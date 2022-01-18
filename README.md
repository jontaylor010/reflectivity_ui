# Magnetic Reflectivity Reduction
[![TRAVISCI](https://travis-ci.org/neutrons/reflectivity_ui.svg?branch=master)](https://travis-ci.org/neutrons/reflectivity_ui)
[![codecov](https://codecov.io/gh/neutrons/reflectivity_ui/branch/master/graph/badge.svg)](https://codecov.io/gh/neutrons/reflectivity_ui)

## v2.0.43 [06/11/2020]
 - Pinned to use mantid42 and python2 fixed
 
## v2.0.42 [05/28/2020]
 - Pinned to use mantid42 and python2

## v2.0.41 [06/29/2019]
 - Minor fixes

## v2.0.40 [02/19/2019]
 - Write calculated angle to data file

## v2.0.39 [02/14/2019]
 - Order cross-sections starting with off-off
 - Fix issue with 3rd cross-section not displaying when only three are measured.

## v2.0.38 [02/12/2019]
 - Fix issue with nan's appearing with fine binning of off-specular

## v2.0.37 [02/11/2019]
 - Improve off-specular slices

## v2.0.36 [02/07/2019]
 - Result preview improvements (sync zoom)
 - Off-spec UI improvements: separate smoothing from the rest
 - Add smoothing dialog for pick options interactively on a plot
 - Email option [data only]
 - When stitching, pick the cross-section with highest counts in overlap
 - Add GISANS result tiles, with sync zoom
 - Add smart stitch that picks the cross-section with highest stats at the overlap
 - Tweak size for smaller screens
 - Display Qz bin width when binning off-spec
 - Improve output python script

## v2.0.35 [01/24/2019]
 - Add result preview

## v2.0.34
 - Make sure spin asymmetry work when not rebinning.
 - Remove the option to use the data's TOF range because it creates problems when combining data (like spin asymmetry).

## v2.0.33
 - Hybrid spin boxes to test out synching to plots and responsiveness.
 - Background selection is now remembered from run to run upon loading.
 - Selecting a very wide wavelength band will pick the actual band in the data.
 - Made sure cutting TOF bins matches between specular (not rebinned) and off-specular
 - Updated wavelength band.

## Developer Instructions

### How to start the GUI on the analysis cluster

This app `QuickNXS` requires an ancient version of `Mantid` (Mantid42), therefore the development needs to be performed on the analysis cluster where the proper version is instaled.
To start the app as a developer, please follow the following steps:

- Disable your customized conda environment as `QuickNXS` needs to use the system python2.7.
- Clone the repo as usual (use ssh or access token per Github requirement)
- Go to the root of the repo and do a dirty install with `python setup.py install --user`.
  - This unfortunately will affect you local python2 env located in your home directory.
- To start the app, simply do `mantidpython42 --classic bin/quicknxs2` at the root of the repo
  - Missing the argument `--classic` might result in a black screen of QuickNXS.

> NOTE: the instruction above is only valid until the starting of the moderniazation process.
