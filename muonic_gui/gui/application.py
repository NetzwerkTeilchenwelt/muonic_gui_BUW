# -*- coding: utf-8 -*-
"""
Provides the main window for the gui part of muonic
"""
from os import path
from PyQt5.QtWidgets import *
import datetime
import threading
import time
import uuid
import webbrowser

from PyQt5 import QtGui, QtWidgets
from PyQt5 import QtCore, QtWidgets

from muonic import __version__, __source_location__
from muonic import __docs_hosted_at__, __manual_hosted_at__
# from muonic.analysis import PulseExtractor
# from muonic.daq import DAQIOError
from muonic.lib.app import App
from muonic.lib.analyzers import BaseAnalyzer, DummyAnalyzer, RateAnalyzer, PulseAnalyzer, DecayAnalyzer, VelocityAnalyzer
from muonic.lib.consumers import AbstractMuonicConsumer, BufferedConsumer
from muonic_gui.gui.helpers import set_large_plot_style
from muonic_gui.gui.dialogs import ThresholdDialog, ConfigDialog
from muonic_gui.gui.dialogs import HelpDialog, AdvancedDialog
from muonic_gui.gui.widgets import VelocityWidget, PulseAnalyzerWidget
from muonic_gui.gui.widgets import DecayWidget, DAQWidget, RateWidget
from muonic_gui.gui.widgets import GPSWidget, StatusWidget
# from muonic.util import update_setting, get_setting
# from muonic.util import apply_default_settings, get_muonic_filename
# from muonic.util import get_data_directory


class Application(AbstractMuonicConsumer, QtWidgets.QMainWindow):
    """
    The GUI main application

    :param logger: logger object
    :type logger: logging.Logger
    :param opts: command line options
    :type opts: Namespace
    """
    def __init__(self, logger, opts, consumers):

        # call parent class init functions
        # App.__init__(self, opts, analyzers, logger)
        AbstractMuonicConsumer.__init__(self, logger=logger)
        QtWidgets.QMainWindow.__init__(self)

        # start time of the application
        self.start_time = datetime.datetime.utcnow()

        QtCore.QLocale.setDefault(QtCore.QLocale("en_us"))
        self.setWindowTitle("muonic")
        self.setWindowIcon(QtGui.QIcon(path.join(path.dirname(__file__),
                                                   "muonic.xpm")))

        # params
        self.opts = opts

        # tab widget to hold the different physics widgets
        self.tab_widget = QtWidgets.QTabWidget(self)

        # widget store for the tab widgets to reference later
        self._widgets = dict()

        # setup status bar
        self.status_bar = QtWidgets.QMainWindow.statusBar(self)

        # detected pulses
        self.pulses = None

        # create tabbed widgets
        self.setup_tab_widgets(opts)

        self.setCentralWidget(self.tab_widget)

        # widgets which should be calculated in process_incoming.
        # The widget is only calculated when it is set to active (True)
        # via widget.active(True). only widgets which need pulses go here
        # self.pulse_widgets = [self.get_widget("pulse"),
        #                       self.get_widget("decay"),
        #                       self.get_widget("velocity")]

        # widgets which should be dynamically updated by the timer
        # should be in this list
        # self.dynamic_widgets = [self.get_widget("rate"),
        #                         self.get_widget("pulse"),
        #                         self.get_widget("decay"),
        #                         self.get_widget("velocity")]

        # timer to periodically call processIncoming and check
        # what is in the queue
        # self.timer = QtCore.QTimer()
        # QtCore.QObject.connect(self.timer,
        #                        QtCore.SIGNAL("timeout()"),
        #                        self.process_incoming)

        # time update widgets the have dynamic plots in them
        # self.widget_updater = QtCore.QTimer()
        # QtCore.QObject.connect(self.widget_updater,
        #                        QtCore.SIGNAL("timeout()"),
        #                        self.update_dynamic)

        self.daq_log = ""

        self.daq_log_timer = QtCore.QTimer()
        self.daq_log_timer.timeout.connect(self.update_raw_daq)

        self.daq_log_timer.start(1500)

        self.logger.info("Time window is %4.2f" % opts.get("time_window"))

        self.setup_plot_style()
        self.setup_menus()
        # self.process_incoming()

        # start update timers
        # self.timer.start(1000)
        # self.widget_updater.start(opts.time_window * 1000)

        self._consumers = consumers
        self._consumers.append(self)

        # bf = [BufferedConsumer(opts.get("buf_size"), *(self._consumers))]

        self._analyzers = [DummyAnalyzer(logger=logger, consumers=self._consumers, **opts),
                           RateAnalyzer(logger=logger, consumers=self._consumers, **opts),
                           PulseAnalyzer(logger=logger, consumers=self._consumers, **opts),
                           DecayAnalyzer(logger=logger, consumers=self._consumers, **opts),
                           VelocityAnalyzer(logger=logger, consumers=self._consumers, **opts)]

        for a in self._analyzers:
            if isinstance(a, BaseAnalyzer) and not isinstance(a, DummyAnalyzer):
                a.disabled = True

        self._app = App(options=opts, analyzers=self._analyzers, logger=logger)
        self._app_thread = threading.Thread(target=self._app.run)
        self._app_thread.start()

        time.sleep(1.0)

    def setup_tab_widgets(self, opts):
        """
        Creates the widgets and adds tabs

        :returns: None
        """
        self.add_widget("rate", "Muon Rates",
                        RateWidget(self.logger, opts, parent=self))
        self.add_widget("pulse", "Pulse Analyzer",
                        PulseAnalyzerWidget(self.logger, opts, parent=self))
        self.add_widget("decay", "Muon Decay",
                        DecayWidget(self.logger, opts, parent=self))
        self.add_widget("velocity", "Muon Velocity",
                        VelocityWidget(self.logger, opts, parent=self))
        self.add_widget("status", "Status",
                        StatusWidget(self.logger, parent=self))
        self.add_widget("daq", "DAQ Output",
                        DAQWidget(self.logger, parent=self))
        self.add_widget("gps", "GPS Output",
                        GPSWidget(self.logger, parent=self))

    def setup_plot_style(self):
        """
        Setup the plot style depending on screen size.

        :returns: None
        """
        desktop = QtWidgets.QDesktopWidget()
        screen_size = QtCore.QRectF(desktop.screenGeometry(
                desktop.primaryScreen()))
        screen_x = screen_size.x() + screen_size.width()
        screen_y = screen_size.y() + screen_size.height()

        self.logger.info("Screen with size %i x %i detected!" %
                         (screen_x, screen_y))

        # Screens lager than 1600*1200 use large plot style.
        if screen_x * screen_y >= 1920000:
            set_large_plot_style()

    def setup_menus(self):
        """
        Setup the menu bar and populate menus.

        :returns: None
        """
        # create the menubar
        menu_bar = self.menuBar()

        # create file menu
        file_menu = menu_bar.addMenu('&File')

        muonic_data_action = QtWidgets.QAction('Open Data Folder', self)
        muonic_data_action.setStatusTip('Open the folder with the data files written by muonic.')
        muonic_data_action.setShortcut('Ctrl+O')
        muonic_data_action.triggered.connect(self.open_muonic_data)

        file_menu.addAction(muonic_data_action)

        exit_action = QtWidgets.QAction(QtGui.QIcon(
                "/usr/share/icons/gnome/24x24/actions/exit.png"), 'Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close_application)

        file_menu.addAction(exit_action)

        # create settings menu
        settings_menu = menu_bar.addMenu('&Settings')

        config_action = QtWidgets.QAction('Channel Configuration', self)
        config_action.setStatusTip('Configure the Coincidences and channels')
        config_action.triggered.connect(self.config_menu)

        thresholds_action = QtWidgets.QAction('Thresholds', self)
        thresholds_action.setStatusTip('Set trigger thresholds')
        thresholds_action.triggered.connect(self.threshold_menu)

        advanced_action = QtWidgets.QAction('Advanced Configurations', self)
        advanced_action.setStatusTip('Advanced configurations')
        advanced_action.triggered.connect(self.advanced_menu)

        settings_menu.addAction(config_action)
        settings_menu.addAction(thresholds_action)
        settings_menu.addAction(advanced_action)

        # create help menu
        help_menu = menu_bar.addMenu('&Help')

        manualdoc_action = QtWidgets.QAction('Website with Manual', self)
        manualdoc_action.triggered.connect(self.manualdoc_menu)

        sphinxdoc_action = QtWidgets.QAction('Technical documentation', self)
        sphinxdoc_action.triggered.connect(self.sphinxdoc_menu)

        commands_action = QtWidgets.QAction('DAQ Commands', self)
        commands_action.setShortcut('F1')
        commands_action.triggered.connect(self.help_menu)

        about_action = QtWidgets.QAction('About muonic', self)
        about_action.triggered.connect(self.about_menu)

        help_menu.addAction(manualdoc_action)
        help_menu.addAction(commands_action)
        help_menu.addAction(sphinxdoc_action)
        help_menu.addAction(about_action)


    def add_widget(self, name, label, widget):
        """
        Adds widget to the store.

        Raises WidgetWithNameExistsError if a widget of that name already
        exists and TypeError if widget is no subclass of QtGui.QWidget.

        :param name: widget name
        :type name: str
        :param label: the tab label
        :type label: str
        :param widget: widget object
        :type widget: object
        :returns: None
        :raises: WidgetWithNameExistsError, TypeError
        """

        if widget is None:
            return
        if self.have_widget(name):
            raise WidgetWithNameExistsError("widget with name '%s' already exists" % name)
        else:
            if not isinstance(widget, QtWidgets.QWidget):
                raise TypeError("widget has to be a subclass 'QtGui.QWidget'")
                lastWindowClosed = QtCore.pyqtSignal()
            else:
                self.tab_widget.addTab(widget, label)
                self._widgets[name] = widget

    def have_widget(self, name):
        """
        Returns true if widget with name exists, False otherwise.

        :param name: widget name
        :type name: str
        :returns: bool
        """
        return name in self._widgets

    def get_widget(self, name):
        """
        Retrieved a widget from the store.

        :param name: widget name
        :type name: str
        :returns: object
        """
        return self._widgets.get(name)

    def is_widget_active(self, name):
        """
        Returns True if the widget exists and is active, False otherwise

        :param name: widget name
        :type name: str
        :returns: bool
        """
        if self.have_widget(name):
            return self.get_widget(name).active()
        return False

    def threshold_menu(self):
        """
        Shows thresholds dialog.

        :returns: None
        """
        # get the actual thresholds from the DAQ card
        self._app.daq.put('TL')

        # wait explicitly until the thresholds get loaded
        self.logger.info("loading threshold information..")
        time.sleep(1.5)

        # get thresholds from settings
        thresholds = [self._app.get_setting("threshold_ch%d" % i, 300) for i in range(4)]

        # show dialog
        dialog = ThresholdDialog(thresholds)

        if dialog.exec_() == 1:
            commands = []

            # update thresholds config
            for ch in range(4):
                val = dialog.get_widget_value("threshold_ch_%d" % ch)
                self._app.update_setting("threshold_ch%d" % ch, val)
                commands.append("TL %d %s" % (ch, val))

            # apply new thresholds to daq card
            for cmd in commands:
                self._app.daq.put(cmd)
                self.logger.info("Set threshold of channel %s to %s" %
                                 (cmd.split()[1], cmd.split()[2]))

        self._app.daq.put('TL')

    def open_muonic_data(self):
        """
        Opens the folder with the data files. Usually in $HOME/muonic_data
        """

        import webbrowser
        webbrowser.open("file://" + path.expanduser("~") + "/muonic_data/")

    def config_menu(self):
        """
        Show the channel config dialog.

        :returns: None
        """
        # get the actual channels from the DAQ card
        self._app.daq.put("DC")

        # wait explicitly until the channels get loaded
        self.logger.info("loading channel information...")
        time.sleep(1)

        # get current config values
        channel_config = [self._app.get_setting("active_ch%d" % i) for i in range(4)]
        coincidence_config = [self._app.get_setting("coincidence%d" % i)
                              for i in range(4)]
        veto = self._app.get_setting("veto")
        veto_config = [self._app.get_setting("veto_ch%d" % i) for i in range(3)]

        # show dialog
        dialog = ConfigDialog(channel_config, coincidence_config,
                              veto, veto_config)

        if dialog.exec_() == 1:

            # get and update channel and coincidence config
            for i in range(4):
                channel_config[i] = dialog.get_widget_value(
                        "channel_checkbox_%d" % i)
                coincidence_config[i] = dialog.get_widget_value(
                        "coincidence_checkbox_%d" % i)

                self._app.update_setting("active_ch%d" % i, channel_config[i])
                self._app.update_setting("coincidence%d" % i, coincidence_config[i])

            # get and update veto state
            veto = dialog.get_widget_value("veto_checkbox")
            self._app.update_setting("veto", veto)

            # get and update veto channel config
            for i in range(3):
                veto_config[i] = dialog.get_widget_value(
                        "veto_checkbox_%d" % i)

                self._app.update_setting("veto_ch%d" % i, veto_config[i])

            # build daq message to apply the new config to the card
            tmp_msg = ""

            if veto:
                if veto_config[0]:
                    tmp_msg += "01"
                elif veto_config[1]:
                    tmp_msg += "10"
                elif veto_config[2]:
                    tmp_msg += "11"
                else:
                    tmp_msg += "00"
            else:
                tmp_msg += "00"

            coincidence_set = False

            # singles, twofold, threefold, fourfold
            for i, coincidence in enumerate(["00", "01", "10", "11"]):
                if coincidence_config[i]:
                    tmp_msg += coincidence
                    coincidence_set = True

            if not coincidence_set:
                tmp_msg += "00"

            # now calculate the correct expression for the first
            # four bits
            self.logger.debug("The first four bits are set to %s" % tmp_msg)
            msg = "WC 00 %s" % hex(int(''.join(tmp_msg), 2))[-1].capitalize()

            channel_set = False
            enable = ['0', '0', '0', '0']

            for i, active in enumerate(reversed(channel_config)):
                if active:
                    enable[i] = '1'
                    channel_set = True

            if channel_set:
                msg += hex(int(''.join(enable), 2))[-1].capitalize()
            else:
                msg += '0'

            # send the message to the daq card
            self._app.daq.put(msg)

            self.logger.info("The following message was sent to DAQ: %s" % msg)

            for i in range(4):
                self.logger.debug("channel%d selected %s" %
                                  (i, channel_config[i]))

            for i, name in enumerate(["singles", "twofold",
                                      "threefold", "fourfold"]):
                self.logger.debug("coincidence %s %s" %
                                  (name, coincidence_config[i]))

        self._app.daq.put("DC")

    def advanced_menu(self):
        """
        Show a config dialog for advanced options, ie. gate width,
        interval for the rate measurement, options for writing pulse file
        and the write_daq_status option.

        :returns: None
        """
        # get the actual channels from the DAQ card
        self._app.daq.put("DC")

        # wait explicitly until the channels get loaded
        self.logger.info("loading channel information...")
        time.sleep(1)

        # show dialog
        dialog = AdvancedDialog(self._app.get_setting("gate_width"),
                                self._app.get_setting("time_window"),
                                self._app.get_setting("write_daq_status"))

        if dialog.exec_() == 1:
            # update time window
            time_window = float(dialog.get_widget_value("time_window"))

            if time_window < 0.01 or time_window > 10000.:
                self.logger.warning("Time window too small or too big, " +
                                    "resetting to 5 s.")
                time_window = 5.0

            self._app.update_setting("time_window", time_window)

            # update write_daq_status
            write_daq_status = dialog.get_widget_value("write_daq_status")
            self._app.update_setting("write_daq_status", write_daq_status)

            # update gate width
            gate_width = int(dialog.get_widget_value("gate_width"))
            self._app.update_setting("gate_width", gate_width)

            # transform gate width for daq msg
            gate_width = bin(gate_width // 10).replace('0b', '').zfill(16)
            gate_width_03 = format(int(gate_width[0:8], 2), 'x').zfill(2)
            gate_width_02 = format(int(gate_width[8:16], 2), 'x').zfill(2)

            # set gate widths
            self._app.daq.put("WC 03 %s" % gate_width_03)
            self._app.daq.put("WC 02 %s" % gate_width_02)

            # adjust the update interval
            self.widget_updater.start(time_window * 1000)

            self.logger.debug("Writing gate width WC 02 %s WC 03 %s" %
                              (gate_width_02, gate_width_03))
            self.logger.debug("Setting time window to %.2f " % time_window)
            self.logger.debug("Switching write_daq_status option to %s" %
                              write_daq_status)

        self._app.daq.put("DC")

    def help_menu(self):
        """
        Show a simple help dialog.

        :returns: None
        """
        HelpDialog().exec_()

    def about_menu(self):
        """
        Show a link to the online documentation.

        :returns: None
        """
        QtWidgets.QMessageBox.information(self, "about muonic",
                                      "version: %s\n source located at: %s" %
                                      (__version__, __source_location__))

    def sphinxdoc_menu(self):
        """
        Show the sphinx documentation that comes with muonic in a
        browser.

        :returns: None
        """
        docs = __docs_hosted_at__

        self.logger.debug("Opening docs from %s" % docs)

        if not webbrowser.open(docs):
            self.logger.warning("Can not open webbrowser! " +
                                "Browse to %s to see the docs" % docs)

    def manualdoc_menu(self):
        """
        Show the manual that comes with muonic in a pdf viewer.

        :returns: None
        """
        docs = __manual_hosted_at__

        self.logger.info("Opening docs from %s" % docs)

        if not webbrowser.open(docs):
            self.logger.warning("Can not open PDF reader!")

    # def calculate_pulses(self):
    #     """
    #     Runs the calculate function of pulse widgets if they are active
    #     and pulses are available.
    #
    #     :returns: None
    #     """
    #     for widget in self.pulse_widgets:
    #         if widget.active() and (self.pulses is not None):
    #             widget.calculate(self.pulses)

    # def update_dynamic(self):
    #     """
    #     Update dynamic widgets.
    #
    #     :returns: None
    #     """
    #     for widget in self.dynamic_widgets:
    #         if widget.active():
    #             widget.update()

    def closeEvent(self, ev):
        """
        Is triggered when it is attempted to close the application.
        Will perform some cleanup before closing.

        :param ev: event
        :type ev: QtGui.QCloseEvent
        :returns: None
        """
        self.logger.info("Attempting to close application")

        # ask kindly if the user is really sure if she/he wants to exit
        reply = QtWidgets.QMessageBox.question(self, "Attention!",
                                           "Do you really want to exit?",
                                           QtWidgets.QMessageBox.Yes |
                                           QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            # self.timer.stop()
            # self.widget_updater.stop()

            for key, widget in self._widgets.items():
                # run finish hook on each widget, e.g. close and
                # rename files if necessary
                widget.finish()

            # run finish hook on pulse extractor to close and
            # rename pulse file
            # self.pulse_extractor.finish()

            self._app.stop()
            self._app_thread.join(timeout=10.0)

            time.sleep(0.5)

            self.lastWindowClosed.emit()
            ev.accept()
        else:
            # don't close the application
            ev.ignore()

    def run(self, run_id=None):

        # if not run_id:
        #     run_id = uuid.uuid4()
        # self.logger.info('Analyzers: %s' % [x.__class__.__name__ for x in self.analyzers if isinstance(x, BaseAnalyzer)])
        self.running = True
        # start_ts = datetime.datetime.utcnow()
        # duration = self.get_setting('meas_duration')

    def push_raw(self, data, meta):
        # print("DEBUG Application.push_raw START")

        self.daq_log += data + "\n"

        # print("DEBUG Application.push_raw END")

    def update_raw_daq(self):
        self.get_widget("daq").daq_msg_log.appendPlainText(self.daq_log)

        self.daq_log = ""

    def push_pulse(self, pulse_widths, event_time, meta):
        w = self.get_widget("pulse")

        for i in range(4):
            w.pulse_width_canvases[i].update_plot(pulse_widths[i])

    def push_rate(self, rates, counts, time_window, query_time, meta):
        # print("DEBUG Application.push_rate START")

        w = self.get_widget("rate")

        w.update_info_field("max_rate", "%.3f 1/s" % rates[5])

        data = rates[0:5]
        data.append(time_window)
        w.scalars_monitor.update_plot(data)
        w.update_info_field("daq_time", "%.2f s" % time_window)

        for i in range(5):
            w.rate_fields[i].setText("%.3f" % rates[i])
            w.scalar_fields[i].setText("%d" % counts[i])

        # print("DEBUG Application.push_rate END")

    def push_decay(self, decay_time, event_time, meta):
        w = self.get_widget("decay")

        w.plot_canvas.update_plot([decay_time])

    def push_velocity(self, flight_time, event_time, meta):
        w = self.get_widget("velocity")

        w.plot_canvas.update_plot([flight_time])


class WidgetWithNameExistsError(Exception):
    """
    Exception that gets raised if it is attempted to overwrite a
    widget reference that already exists.
    """
    pass
