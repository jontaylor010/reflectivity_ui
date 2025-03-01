# coding: utf-8
"""
   Dialog to let the user select smoothing options
   This code was taken as-is from QuickNXS v1
"""
# pylint: disable=bare-except

from PyQt5 import QtWidgets

from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse

from .configuration import Configuration
from reflectivity_ui.interfaces import load_ui


class SmoothDialog(QtWidgets.QDialog):
    """
    Dialog to define smoothing parameters.
    """

    drawing = False

    def __init__(self, parent, data_manager):
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = load_ui("ui_smooth_dialog.ui", baseinstance=self)
        self.data_manager = data_manager
        self.ui.plot.canvas.mpl_connect("motion_notify_event", self.plotSelect)
        self.ui.plot.canvas.mpl_connect("button_press_event", self.plotSelect)
        self.drawPlot()

    def drawPlot(self):
        """
        Plot the unsmoothed data.
        """
        self.drawing = True
        plot = self.ui.plot
        plot.clear()
        Qzmax = 0.001

        # Get data from first cross-section.
        first_state = self.data_manager.reduction_states[0]

        # Get it the way that the plot manager does.

        for item in self.data_manager.reduction_list:
            offspec = item.cross_sections[first_state].off_spec
            Qx, Qz, ki_z, kf_z, I, _ = (offspec.Qx, offspec.Qz, offspec.ki_z, offspec.kf_z, offspec.S, offspec.dS)

            n_total = len(I[0])
            # P_0 and P_N are the number of points to cut in TOF on each side
            p_0 = item.cross_sections[first_state].configuration.cut_first_n_points
            p_n = n_total - item.cross_sections[first_state].configuration.cut_last_n_points
            Qx = Qx[:, p_0:p_n]
            Qz = Qz[:, p_0:p_n]
            ki_z = ki_z[:, p_0:p_n]
            kf_z = kf_z[:, p_0:p_n]
            I = I[:, p_0:p_n]

            Qzmax = max(ki_z.max() * 2.0, Qzmax)
            if self.ui.kizmkfzVSqz.isChecked():
                plot.pcolormesh((ki_z - kf_z), Qz, I, log=True, imin=1e-6, imax=1.0, shading="gouraud")
            elif self.ui.qxVSqz.isChecked():
                plot.pcolormesh(Qx, Qz, I, log=True, imin=1e-6, imax=1.0, shading="gouraud")
            else:
                plot.pcolormesh(ki_z, kf_z, I, log=True, imin=1e-6, imax=1.0, shading="gouraud")

        if self.ui.kizmkfzVSqz.isChecked():
            plot.canvas.ax.set_xlim([-0.035, 0.035])
            plot.canvas.ax.set_ylim([0.0, Qzmax * 1.01])
            plot.set_xlabel("k$_{i,z}$-k$_{f,z}$ [Å$^{-1}$]")
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]")
            x1 = -0.03
            x2 = 0.03
            y1 = 0.0
            y2 = Qzmax
            sigma_pos = (0.0, Qzmax / 3.0)
            sigma_ang = 0.0
            self.ui.sigmasCoupled.setChecked(True)
            self.ui.sigmaY.setEnabled(False)
            self.ui.sigmaX.setValue(0.0005)
            self.ui.sigmaY.setValue(0.0005)
        elif self.ui.qxVSqz.isChecked():
            plot.canvas.ax.set_xlim([-0.0005, 0.0005])
            plot.canvas.ax.set_ylim([0.0, Qzmax * 1.01])
            plot.set_xlabel("Q$_x$ [Å$^{-1}$]")
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]")
            x1 = -0.0002
            x2 = 0.0002
            y1 = 0.0
            y2 = Qzmax
            sigma_pos = (0.0, Qzmax / 3.0)
            sigma_ang = 0.0
            self.ui.sigmasCoupled.setChecked(False)
            self.ui.sigmaY.setEnabled(True)
            self.ui.sigmaX.setValue(0.00001)
            self.ui.sigmaY.setValue(0.0005)
        else:
            plot.canvas.ax.set_xlim([0.0, Qzmax / 2.0 * 1.01])
            plot.canvas.ax.set_ylim([0.0, Qzmax / 2.0 * 1.01])
            plot.set_xlabel("k$_{i,z}$ [Å$^{-1}$]")
            plot.set_ylabel("k$_{f,z}$ [Å$^{-1}$]")
            x1 = 0.0
            x2 = Qzmax / 2.0
            y1 = 0.0
            y2 = Qzmax / 2.0
            sigma_pos = (Qzmax / 6.0, Qzmax / 6.0)
            sigma_ang = 0.0  # -45.
            self.ui.sigmasCoupled.setChecked(True)
            self.ui.sigmaX.setValue(0.0005)
            self.ui.sigmaY.setValue(0.0005)
        if plot.cplot is not None:
            plot.cplot.set_clim([1e-6, 1.0])
        self.rect_region = Line2D([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        self.sigma_1 = Ellipse(
            sigma_pos, self.ui.sigmaX.value() * 2, self.ui.sigmaY.value() * 2, sigma_ang, fill=False
        )
        self.sigma_2 = Ellipse(
            sigma_pos, self.ui.sigmaX.value() * 4, self.ui.sigmaY.value() * 4, sigma_ang, fill=False
        )
        self.sigma_3 = Ellipse(
            sigma_pos, self.ui.sigmaX.value() * 6, self.ui.sigmaY.value() * 6, sigma_ang, fill=False
        )
        plot.canvas.ax.add_line(self.rect_region)
        plot.canvas.ax.add_artist(self.sigma_1)
        plot.canvas.ax.add_artist(self.sigma_2)
        plot.canvas.ax.add_artist(self.sigma_3)
        plot.draw()
        # set parameter values
        self.ui.gridXmin.setValue(x1)
        self.ui.gridXmax.setValue(x2)
        self.ui.gridYmin.setValue(y1)
        self.ui.gridYmax.setValue(y2)
        self.updateGrid()
        self.drawing = False

    def updateSettings(self):
        if self.drawing:
            return
        self.drawing = True
        if self.ui.sigmasCoupled.isChecked():
            self.ui.sigmaY.setValue(self.ui.sigmaX.value())
        self.updateGrid()
        # redraw indicators
        x1 = self.ui.gridXmin.value()
        x2 = self.ui.gridXmax.value()
        y1 = self.ui.gridYmin.value()
        y2 = self.ui.gridYmax.value()
        self.rect_region.set_data([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        self.sigma_1.width = 2 * self.ui.sigmaX.value()
        self.sigma_1.height = 2 * self.ui.sigmaY.value()
        self.sigma_2.width = 4 * self.ui.sigmaX.value()
        self.sigma_2.height = 4 * self.ui.sigmaY.value()
        self.sigma_3.width = 6 * self.ui.sigmaX.value()
        self.sigma_3.height = 6 * self.ui.sigmaY.value()
        self.ui.plot.draw()
        self.drawing = False

    def updateGrid(self):
        if self.ui.gridSizeCoupled.isChecked():
            sx = self.ui.sigmaX.value()
            sy = self.ui.sigmaY.value()
            x1 = self.ui.gridXmin.value()
            x2 = self.ui.gridXmax.value()
            y1 = self.ui.gridYmin.value()
            y2 = self.ui.gridYmax.value()
            self.ui.gridSizeX.setValue(int((x2 - x1) / sx * 1.41))
            self.ui.gridSizeY.setValue(int((y2 - y1) / sy * 1.41))

    def plotSelect(self, event):
        """
        Plot for y-projection has been clicked.
        """
        # if event.button == 1 and self.ui.plot.toolbar._active is None and event.xdata is not None:
        if event.button == 1 and event.xdata is not None:
            x = event.xdata
            y = event.ydata
            x1 = self.ui.gridXmin.value()
            x2 = self.ui.gridXmax.value()
            y1 = self.ui.gridYmin.value()
            y2 = self.ui.gridYmax.value()
            if x < x1 or abs(x - x1) < abs(x - x2):
                x1 = x
            else:
                x2 = x
            if y < y1 or abs(y - y1) < abs(y - y2):
                y1 = y
            else:
                y2 = y
            self.drawing = True
            self.ui.gridXmin.setValue(x1)
            self.ui.gridXmax.setValue(x2)
            self.ui.gridYmin.setValue(y1)
            self.ui.gridYmax.setValue(y2)
            self.drawing = False
            self.updateSettings()

    def update_output_options(self, output_options):
        """
        Update a dict with smoothing options
        :param dict: dictionary object
        """
        if self.ui.kizVSkfz.isChecked():
            output_options["off_spec_x_axis"] = Configuration.KZI_VS_KZF
        elif self.ui.qxVSqz.isChecked():
            output_options["off_spec_x_axis"] = Configuration.QX_VS_QZ
        else:
            output_options["off_spec_x_axis"] = Configuration.DELTA_KZ_VS_QZ

        output_options["off_spec_nxbins"] = self.ui.gridSizeX.value()
        output_options["off_spec_nybins"] = self.ui.gridSizeY.value()

        output_options["off_spec_sigmas"] = self.ui.rSigmas.value()
        output_options["off_spec_sigmax"] = self.ui.sigmaX.value()
        output_options["off_spec_sigmay"] = self.ui.sigmaY.value()
        output_options["off_spec_x_min"] = self.ui.gridXmin.value()
        output_options["off_spec_x_max"] = self.ui.gridXmax.value()
        output_options["off_spec_y_min"] = self.ui.gridYmin.value()
        output_options["off_spec_y_max"] = self.ui.gridYmax.value()

        return output_options
