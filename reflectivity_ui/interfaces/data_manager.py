# pylint: disable=bare-except
"""
    Data manager. Holds information about the current data location
    and manages the data cache.
"""

import glob
import sys
import os
import time
import numpy as np
import logging
from reflectivity_ui.interfaces.data_handling.data_set import NexusData
from reflectivity_ui.interfaces.data_handling.filepath import RunNumbers, FilePath
from .data_handling import data_manipulation
from .data_handling import quicknxs_io
from .data_handling import off_specular
from .data_handling import gisans


class DataManager(object):
    MAX_CACHE = 50  # maximum number of loaded datasets (either single-file or merged-files types)

    def __init__(self, current_directory):
        self.current_directory = current_directory
        # current file name is used for file list table to set the current item
        self.current_file_name = None
        # Current data set
        self._nexus_data = None
        self.active_channel = None  # type: Optional[CrossSectionData]
        # Cache of loaded data: list of NexusData instances
        self._cache = list()  # type: List[NexusData]

        # The following is information about the data to be combined together
        # List of data sets
        self.reduction_list = []  # type: List[NexusData]
        self.direct_beam_list = []  # type: List[NexusData]
        # List of cross-sections common to all reduced data sets
        self.reduction_states = []  # type: List[str]  # List of cross-section states
        self.final_merged_reflectivity = {}

        # Cached outputs
        self.cached_offspec = None
        self.cached_gisans = None

    @property
    def data_sets(self):
        """Reduced cross sections

        Returns
        -------
        dict
            dictionary of cross sections
        """
        if self._nexus_data is None:
            return None
        return self._nexus_data.cross_sections

    @property
    def current_file(self):
        if self._nexus_data is None:
            return None
        return self._nexus_data.file_path

    def get_cachesize(self):
        return len(self._cache)

    def clear_cache(self):
        self._cache = []

    def set_active_data_from_reduction_list(self, index):
        """
        Set a data set in the reduction list as the active
        data set according to its index.
        :param int index: index in the reduction list
        """
        if index < len(self.reduction_list):
            self._nexus_data = self.reduction_list[index]
            self.set_channel(0)

    def set_active_data_from_direct_beam_list(self, index):
        """
        Set a data set in the direct beam list as the active
        data set according to its index.
        :param int index: index in the direct beam list
        """
        if index < len(self.direct_beam_list):
            self._nexus_data = self.direct_beam_list[index]
            self.set_channel(0)

    def set_channel(self, index):
        """Set the current channel to the specified index, or zero
        if it doesn't exist.

        Parameters
        ----------
        index: int
            channel index

        Returns
        -------
        bool

        """
        if self.data_sets is None:
            return False
        channels = list(self.data_sets.keys())
        if index < len(channels):
            # channel index is allowed
            self.active_channel = self.data_sets[channels[index]]
            return True
        elif len(channels) == 0:
            # no channel
            logging.error("Could not set active channel: no data available")
        else:
            # default
            self.active_channel = self.data_sets[channels[0]]

        return False

    def is_active(self, data_set):
        """
        Returns True of the given data set is the active data set.
        :param NexusData: data set object
        """
        return data_set == self._nexus_data

    def is_active_data_compatible(self):
        r"""
        @brief Determine if the currently active data set is compatible with the data sets in the reduction list.
        """
        # If we are starting a new reduction list, just proceed
        if self.reduction_list == []:
            return True

        # First, check that we have the same number of states
        if not len(self.reduction_states) == len(self.data_sets.keys()):
            logging.error(
                "Active data cross-sections ({}) different than those of the"
                " reduction list ({})".format(self.reduction_states, self.data_sets.keys())
            )
            return False

        # Second, make sure the states match
        for cross_section_state in self.data_sets.keys():
            if cross_section_state not in self.reduction_states:
                logging.error(
                    "Active data cross-section {} not found in those"
                    " of the reduction list".format(cross_section_state)
                )
                return False
        return True

    def find_data_in_reduction_list(self, nexus_data):
        """
        Look for the given data in the reduction list.
        Return the index within the reduction list or none.
        :param NexusData: data set object
        """
        for i in range(len(self.reduction_list)):
            if nexus_data == self.reduction_list[i]:
                return i
        return None

    def find_data_in_direct_beam_list(self, nexus_data):
        """
        Look for the given data in the direct beam list.
        Return the index within the direct beam list or none.
        :param NexusData: data set object
        """
        for i in range(len(self.direct_beam_list)):
            if nexus_data == self.direct_beam_list[i]:
                return i
        return None

    def find_active_data_id(self):
        """
        Look for the active data in the reduction list.
        Return the index within the reduction list or none.
        """
        return self.find_data_in_reduction_list(self._nexus_data)

    def find_active_direct_beam_id(self):
        """
        Look for the active data in the direct beam list.
        Return the index within the direct beam list or none.
        """
        return self.find_data_in_direct_beam_list(self._nexus_data)

    def add_active_to_reduction(self):
        r"""
        @brief Add active data set to reduction list
        """
        if self._nexus_data not in self.reduction_list:
            if self.is_active_data_compatible():
                if len(self.reduction_list) == 0:
                    self.reduction_states = list(self.data_sets.keys())
                ws = self._nexus_data.get_reflectivity_workspace_group()[0]
                # Append to the reduction list, but keep the theta ordering
                theta = ws.getRun().getProperty("two_theta").value
                is_inserted = False
                for i in range(len(self.reduction_list)):
                    _ws = self.reduction_list[i].get_reflectivity_workspace_group()[0]
                    _theta = _ws.getRun().getProperty("two_theta").value
                    if theta <= _theta:
                        self.reduction_list.insert(i, self._nexus_data)
                        is_inserted = True
                        break
                if not is_inserted:
                    self.reduction_list.append(self._nexus_data)
                return True
            else:
                logging.error("The data you are trying to add has different cross-sections")
        return False

    def add_active_to_normalization(self):
        """
        Add active data set to the direct beam list
        """
        if not self._nexus_data in self.direct_beam_list:
            self.direct_beam_list.append(self._nexus_data)
            return True
        return False

    def remove_active_from_normalization(self):
        """
        Remove the active data set from the direct beam list
        """
        for i in range(len(self.direct_beam_list)):
            if self.direct_beam_list[i] == self._nexus_data:
                self.direct_beam_list.pop(i)
                return i
        return -1

    def clear_direct_beam_list(self):
        """
        Remove all items from the direct beam list, and make
        sure to remove links to those items in the scattering data sets.

        TODO: remove links from scattering data sets.
        """
        self.direct_beam_list = []

    def _loading_progress(self, call_back, start_value, stop_value, value, message=None):
        _value = start_value + (stop_value - start_value) * value
        call_back(_value, message)

    def load(self, file_path, configuration, force=False, update_parameters=True, progress=None):
        # type: (str, Configuration, Optional[bool], Optional[bool], Optional[ProgressReporter]) -> bool
        r"""
        @brief Load one ore more Nexus data files
        @param file_path: absolute path to one or more files. If more than one, files are concatenated with the
        merge symbol '+'.
        @param configuration: configuration to use to load the data
        @param force: it True, existing data in the cache will be replaced by reading from file.
        @param update_parameters: if True, we will find peak ranges
        @param progress: aggregator to estimate percent of time allotted to this function
        @returns True if the data is retrieved from the cache of past loading events
        """
        # Actions taken in this function:
        # 1. Find if the file has been loaded in the past. Retrieve the cache when force==False
        # 2. If file not in cache, or if force==True: invoke NexusData.load()
        # 3. Update attributes _nexus_data, current_directory, and current_file_name
        # 4. If we're overwriting cached data that was allocated in the reduction_list and direct_beam_list,
        #    then assign the new data to the proper indexes in lists reduction_list and direct_beam_list
        # 5. Compute reflectivity if data is loaded from file

        nexus_data = None  # type: NexusData
        is_from_cache = False  # if True, the file has been loaded before
        reduction_list_id = None
        direct_beam_list_id = None
        file_path = FilePath(file_path, sort=True).path  # force sorting by increasing run number

        if progress is not None:
            progress(10, "Loading data...")

        # Check whether the file has already been loaded (in cache)
        for i in range(len(self._cache)):
            if self._cache[i].file_path == file_path:
                if force:
                    # Check whether the data is in the reduction list before removing it
                    reduction_list_id = self.find_data_in_reduction_list(self._cache[i])
                    direct_beam_list_id = self.find_data_in_direct_beam_list(self._cache[i])
                    self._cache.pop(i)
                else:
                    nexus_data = self._cache[i]
                    is_from_cache = True
                break

        # If we don't have the data, load it
        if nexus_data is None:
            configuration.normalization = None
            nexus_data = NexusData(file_path, configuration)
            sub_task = progress.create_sub_task(max_value=70) if progress else None
            nexus_data.load(progress=sub_task, update_parameters=update_parameters)

        if progress is not None:
            progress(80, "Calculating...")

        if nexus_data is not None:
            self._nexus_data = nexus_data
            # Example: '/SNS/REF_M/IPTS-25531/nexus/REF_M_38198.nxs.h5+/SNS/REF_M/IPTS-25531/nexus/REF_M_38199.nxs.h5'
            # will be split into directory='/SNS/REF_M/IPTS-25531/nexus' and
            # file_name='REF_M_38198.nxs.h5+REF_M_38199.nxs.h5'
            directory, file_name = FilePath(file_path).split()
            self.current_directory = directory
            self.current_file_name = file_name
            self.set_channel(0)

            # If we didn't get this data set from our cache, add it and compute its reflectivity.
            if not is_from_cache:
                # Find suitable direct beam
                logging.info("Direct beam from loader: %s", configuration.normalization)
                if configuration.normalization is None and configuration.match_direct_beam:
                    self.find_best_direct_beam()

                # Replace reduction and normalization entries as needed
                if reduction_list_id is not None:
                    self.reduction_list[reduction_list_id] = nexus_data
                if direct_beam_list_id is not None:
                    self.direct_beam_list[direct_beam_list_id] = nexus_data

                # Compute reflectivity
                try:
                    self.calculate_reflectivity()
                except:
                    logging.error("Reflectivity calculation failed for %s", file_name)

                # if cached reduced data exceeds maximum cache size, remove the oldest reduced data
                while len(self._cache) >= self.MAX_CACHE:
                    self._cache.pop(0)
                self._cache.append(nexus_data)

        if progress is not None:
            progress(100)
        return is_from_cache

    def update_configuration(self, configuration, active_only=False, nexus_data=None):
        """
        Update configuration
        """
        if active_only:
            self.active_channel.update_configuration(configuration)
        elif nexus_data is not None:
            nexus_data.update_configuration(configuration)
        else:
            self._nexus_data.update_configuration(configuration)

    def get_active_direct_beam(self):
        """
        Return the direct beam data object for the active data
        """
        return self._find_direct_beam(self._nexus_data)

    def _find_direct_beam(self, nexus_data):
        """
        Determine whether we have a direct beam data set available
        for a given reflectivity data set.
        The object returned is a CrossSectionData object.

        :param NexusData or CrossSectionData nexus_data: data set to find a direct beam for
        """
        direct_beam = None
        # Find the CrossSectionData object to work with
        if isinstance(nexus_data, NexusData):
            # Get the direct beam info from the configuration
            # All the cross sections should have the same direct beam file.
            data_keys = list(nexus_data.cross_sections.keys())
            if len(data_keys) == 0:
                logging.error("DataManager._find_direct_beam: no data available in NexusData object")
                return
            data_xs = nexus_data.cross_sections[data_keys[0]]
        else:
            data_xs = nexus_data

        if data_xs.configuration is not None and data_xs.configuration.normalization is not None:
            for item in self.direct_beam_list:
                # convert _run_number to int if it can be
                try:
                    _run_number = int(data_xs.configuration.normalization)
                except (ValueError, TypeError):
                    _run_number = data_xs.configuration.normalization
                # convert item.number to int if it can be
                try:
                    item_number = int(item.number)
                except (ValueError, TypeError):
                    item_number = item.number
                if item_number == _run_number:
                    keys = list(item.cross_sections.keys())
                    if len(keys) >= 1:
                        if len(keys) > 1:
                            logging.error("More than one cross-section for the direct beam, using the first one")
                        direct_beam = item.cross_sections[keys[0]]
            if direct_beam is None:
                logging.error("The specified direct beam is not available: skipping")

        return direct_beam

    def reduce_gisans(self, progress=None):
        """
        Since the specular reflectivity is prominently displayed, it is updated as
        soon as parameters change. This is not the case for GISANS, which is
        computed on-demand.
        This method goes through the data sets in the reduction list and re-calculate
        the GISANS.
        """
        if progress is not None:
            progress(1, "Reducing GISANS...")
        for i, nexus_data in enumerate(self.reduction_list):
            try:
                self.calculate_gisans(nexus_data=nexus_data, progress=None)
                if progress is not None:
                    progress(100.0 / len(self.reduction_list) * (i + 1))
            except:
                logging.error("Could not compute GISANS for %s\n  %s", nexus_data.number, sys.exc_info()[1])
        if progress is not None:
            progress(100)

    def calculate_gisans(self, nexus_data=None, progress=None):
        """
        Compute GISANS for a single data set
        """
        t_0 = time.time()
        # Select the data to work on
        if nexus_data is None:
            nexus_data = self._nexus_data

        # We must have a direct beam data set to normalize with
        direct_beam = self._find_direct_beam(nexus_data)
        if direct_beam is None:
            # TODO 67 Handle this error with GUI prompt GUI
            raise RuntimeError("Please select a direct beam data set for your data.")

        nexus_data.calculate_gisans(direct_beam=direct_beam, progress=progress)
        logging.info("Calculate GISANS: %s %s sec", nexus_data.number, (time.time() - t_0))

    def is_offspec_available(self):
        """
        Verify that all data sets and all cross-sections have calculated
        off-specular data available.
        """
        for nexus_data in self.reduction_list:
            if not nexus_data.is_offspec_available():
                return False
        return True

    def is_gisans_available(self, active_only=True):
        """
        Verify that all data sets and all cross-sections have calculated
        GISANS data available.
        """
        if active_only:
            return self._nexus_data.is_gisans_available()

        for nexus_data in self.reduction_list:
            if not nexus_data.is_gisans_available():
                return False
        return True

    def reduce_offspec(self, progress=None):
        """
        Since the specular reflectivity is prominently displayed, it is updated as
        soon as parameters change. This is not the case for the off-specular, which is
        computed on-demand.
        This method goes through the data sets in the reduction list and re-calculate
        the off-specular reflectivity.
        """
        for nexus_data in self.reduction_list:
            try:
                self.calculate_reflectivity(nexus_data=nexus_data, specular=False)
            except:
                logging.error("Could not compute reflectivity for %s\n  %s", nexus_data.number, sys.exc_info()[1])

    def rebin_gisans(self, pol_state, wl_min=0, wl_max=100, qy_npts=50, qz_npts=50, use_pf=False):
        """
        Merge all the off-specular reflectivity data and rebin.
        """
        return gisans.rebin_extract(
            self.reduction_list,
            pol_state=pol_state,
            wl_min=wl_min,
            wl_max=wl_max,
            qy_npts=qy_npts,
            qz_npts=qz_npts,
            use_pf=use_pf,
        )

    # TODO 67 FInd out whether it can work with merged data
    def calculate_reflectivity(self, configuration=None, active_only=False, nexus_data=None, specular=True):
        """
        Calculate reflectivity using the current configuration
        """
        # Select the data to work on
        if nexus_data is None:
            nexus_data = self._nexus_data

        # Try to find the direct beam in the list of direct beam data sets
        direct_beam = self._find_direct_beam(nexus_data)

        if not specular:
            nexus_data.calculate_offspec(direct_beam=direct_beam)
        elif active_only:
            self.active_channel.reflectivity(direct_beam=direct_beam, configuration=configuration)
        else:
            nexus_data.calculate_reflectivity(direct_beam=direct_beam, configuration=configuration)

    def find_best_direct_beam(self):
        """
        Find the best direct beam in the direct beam list for the active data
        Returns a run number.
        Returns True if we have updated the data with a new normalization run.
        """
        # TODO 65+ Can it work with merged data?
        # Select the first run number if the active channel cross section is derived from more than one run
        active_channel_number = RunNumbers(self.active_channel.number).numbers[0]
        closest = None
        for item in self.direct_beam_list:
            item_number = int(item.number)
            xs_keys = list(item.cross_sections.keys())
            if len(xs_keys) > 0:
                channel = item.cross_sections[list(item.cross_sections.keys())[0]]
                if self.active_channel.configuration.instrument.direct_beam_match(self.active_channel, channel):
                    if closest is None:
                        closest = item_number
                    elif abs(item_number - active_channel_number) < abs(closest - active_channel_number):
                        closest = item_number

        if closest is None:
            # If we didn't find a direct beam, try with just the wavelength
            for item in self.direct_beam_list:
                xs_keys = list(item.cross_sections.keys())
                if len(xs_keys) > 0:
                    channel = item.cross_sections[list(item.cross_sections.keys())[0]]
                    if self.active_channel.configuration.instrument.direct_beam_match(
                        self.active_channel, channel, skip_slits=True
                    ):
                        if closest is None:
                            closest = item_number
                        elif abs(item_number - active_channel_number) < abs(closest - active_channel_number):
                            closest = item_number
        if closest is not None:
            return self._nexus_data.set_parameter("normalization", closest)
        return False

    def get_trim_values(self):
        """
        Cut the start and end of the active data set to 5% of its
        maximum intensity.
        """
        if (
            self.active_channel is not None
            and self.active_channel.q is not None
            and self.active_channel.configuration.normalization is not None
        ):
            direct_beam = self._find_direct_beam(self.active_channel)

            if direct_beam is None:
                logging.error("The specified direct beam is not available: skipping")
                return

            region = np.where(direct_beam.r >= (direct_beam.r.max() * 0.05))[0]
            p_0 = region[0]
            p_n = len(direct_beam.r) - region[-1] - 1
            self._nexus_data.set_parameter("cut_first_n_points", p_0)
            self._nexus_data.set_parameter("cut_last_n_points", p_n)
            return [p_0, p_n]
        return

    def strip_overlap(self):
        """
        Remove overlapping points in the reflecitviy, cutting always from the lower Qz
        measurements.
        """
        if len(self.reduction_list) < 2:
            logging.error("You need to have at least two datasets in the reduction table")
            return
        xs = self.active_channel.name
        for idx, item in enumerate(self.reduction_list[:-1]):
            next_item = self.reduction_list[idx + 1]
            end_idx = next_item.cross_sections[xs].configuration.cut_first_n_points

            overlap_idx = np.where(item.cross_sections[xs].q >= next_item.cross_sections[xs].q[end_idx])
            logging.error(overlap_idx[0])
            if len(overlap_idx[0]) > 0:
                n_points = len(item.cross_sections[xs].q) - overlap_idx[0][0]
                item.set_parameter("cut_last_n_points", n_points)

    def stitch_data_sets(self, normalize_to_unity=True, q_cutoff=0.01):
        """
        Determine scaling factors for each data set
        :param bool normalize_to_unity: If True, the reflectivity plateau will be normalized to 1.
        :param float q_cutoff: critical q-value below which we expect R=1
        """
        data_manipulation.smart_stitch_reflectivity(
            self.reduction_list, self.active_channel.name, normalize_to_unity, q_cutoff=q_cutoff
        )

    def merge_data_sets(self, asymmetry=True):
        self.final_merged_reflectivity = {}
        for pol_state in self.reduction_states:
            # The scaling factors should have been determined at this point. Just use them
            # to merge the different runs in a set.
            merged_ws = data_manipulation.merge_reflectivity(
                self.reduction_list, xs=pol_state, q_min=0.001, q_step=-0.01
            )
            self.final_merged_reflectivity[pol_state] = merged_ws

        # Compute asymmetry
        if asymmetry:
            self.asymmetry()

    def determine_asymmetry_states(self):
        """
        Determine which cross-section to use to compute asymmetry.
        """
        # Inspect cross-section
        # - For two states, just calculate the asymmetry using those two
        p_state = None
        m_state = None
        if len(self.reduction_states) == 2:
            if self.reduction_states[0].lower() in ["off_off", "off-off"]:
                p_state = self.reduction_states[0]
                m_state = self.reduction_states[1]
            else:
                p_state = self.reduction_states[1]
                m_state = self.reduction_states[0]
        else:
            _p_state_data = None
            _m_state_data = None
            for item in self.reduction_states:
                if item.lower() in ["off_off", "off-off"]:
                    _p_state_data = item
                if item.lower() in ["on_on", "on-on"]:
                    _m_state_data = item

            if _p_state_data is None or _m_state_data is None:
                _p_state_data = None
                _m_state_data = None
                for item in self.reduction_states:
                    if self.data_sets[item].cross_section_label == "++":
                        _p_state_data = item
                    if self.data_sets[item].cross_section_label == "--":
                        _m_state_data = item

            if _p_state_data is None or _m_state_data is None:
                p_state = None
                m_state = None

        # - If we haven't made sense of it yet, take the first and last cross-sections
        if p_state is None and m_state is None and len(self.reduction_states) >= 2:
            p_state = self.reduction_states[0]
            m_state = self.reduction_states[-1]

        return p_state, m_state

    def asymmetry(self):
        """
        Determine which cross-section to use to compute asymmetry, and compute it.
        """
        p_state, m_state = self.determine_asymmetry_states()

        # Get the list of workspaces
        if p_state in self.final_merged_reflectivity and m_state in self.final_merged_reflectivity:
            p_ws = self.final_merged_reflectivity[p_state]
            m_ws = self.final_merged_reflectivity[m_state]
            ratio_ws = (p_ws - m_ws) / (p_ws + m_ws)

            self.final_merged_reflectivity["SA"] = ratio_ws

    def extract_meta_data(self, file_path=None):
        """
        Return the current q-value at the center of the wavelength range of the current data set.
        If a file path is provided, the mid q-value will be extracted from that data file.
        """
        if file_path is not None:
            return data_manipulation.extract_meta_data(
                file_path=file_path, configuration=self.active_channel.configuration
            )
        return data_manipulation.extract_meta_data(cross_section_data=self.active_channel)

    def load_data_from_reduced_file(self, file_path, configuration=None, progress=None):
        """
        Load the information from a reduced file, the load the data.
        Ask the main event handler to update the UI once we are done.
        :param str file_path: reduced file to load
        :param Configuration configuration: configuration to base the loaded data on
        """
        t_0 = time.time()
        db_files, data_files = quicknxs_io.read_reduced_file(file_path, configuration)
        logging.info("Reduced file loaded: %s sec", time.time() - t_0)

        n_loaded = 0
        n_total = len(db_files) + len(data_files)
        if progress and n_total > 0:
            progress.set_value(1, message="Loaded %s" % os.path.basename(file_path), out_of=n_total)
        for r_id, run_file, conf in db_files:
            t_i = time.time()
            if os.path.isfile(run_file):
                is_from_cache = self.load(run_file, conf, update_parameters=False)
                if is_from_cache:
                    configuration.normalization = None
                    self._nexus_data.update_configuration(conf)
                self.add_active_to_normalization()
                logging.info("%s loaded: %s sec [%s]", r_id, time.time() - t_i, time.time() - t_0)
                if progress:
                    progress.set_value(n_loaded, message="%s loaded" % os.path.basename(run_file), out_of=n_total)
            else:
                logging.error("File does not exist: %s", run_file)
                if progress:
                    progress.set_value(n_loaded, message="ERROR: %s does not exist" % run_file, out_of=n_total)
            n_loaded += 1

        for r_id, run_file, conf in data_files:
            t_i = time.time()
            do_files_exist = []
            for name in run_file.split("+"):
                do_files_exist.append((os.path.isfile(name)))

            if all(do_files_exist):
                is_from_cache = self.load(run_file, conf, update_parameters=False)
                if is_from_cache:
                    configuration.normalization = None
                    self._nexus_data.update_configuration(conf)
                    self.calculate_reflectivity()
                self.add_active_to_reduction()
                logging.info("%s loaded: %s sec [%s]", r_id, time.time() - t_i, time.time() - t_0)
                if progress:
                    progress.set_value(n_loaded, message="%s loaded" % os.path.basename(run_file), out_of=n_total)
            else:
                logging.error("File does not exist: %s", run_file)
                if progress:
                    progress.set_value(n_loaded, message="ERROR: %s does not exist" % run_file, out_of=n_total)
            n_loaded += 1

        if progress:
            progress.set_value(n_total, message="Done", out_of=n_total)

        logging.info("DONE: %s sec", time.time() - t_0)

    @property
    def current_event_files(self):
        # type: () -> List[str]
        r"""
        @brief Sorted list of event files in the current directory
        @details return only file names with pattern '*event.nxs' or '*.nxs.h5'
        """
        event_file_list = glob.glob(os.path.join(self.current_directory, "*event.nxs"))
        h5_file_list = glob.glob(os.path.join(self.current_directory, "*.nxs.h5"))
        event_file_list.extend(h5_file_list)
        return sorted([os.path.basename(name) for name in event_file_list])
