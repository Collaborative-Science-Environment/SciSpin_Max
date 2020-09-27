import Settings
import socket
import board
import busio
import os
import timeit
import time
import Commands
import adafruit_mma8451
import adafruit_bme280

from time import sleep
from PyQt5.QtCore import QThread, pyqtSignal
from picamera import PiCamera


class Cycle(QThread):

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self._running = False

    def run(self):
        if Settings.IR_STAT:
            Settings.sendCMD(Settings.lighting_addr, "3~")
        Commands.clear_lights()
        sleep(1)
        for x in Settings.commands_list:
            cmd = "4~" + x
            Settings.sendCMD(Settings.lighting_addr, cmd)
            sleep(0.1)
        Settings.sendCMD(Settings.lighting_addr, "5~")
        if Settings.IR_STAT:
            sleep(0.1)
            Settings.sendCMD(Settings.lighting_addr, "3~")
        on_stat = True

        while True:
            for x in range(Settings.cycle_time * 60):
                sleep(1)

                if not Settings.cycle_running:
                    on_stat = False
                    break

            if on_stat:
                if Settings.IR_STAT:
                    Settings.sendCMD(Settings.lighting_addr, "3~")
                Commands.clear_lights()
                on_stat = False
            else:
                for i in Settings.commands_list:
                    cmd = "4~" + i
                    Settings.sendCMD(Settings.lighting_addr, cmd)
                    sleep(0.1)
                Settings.sendCMD(Settings.lighting_addr, "5~")
                if Settings.IR_STAT:
                    sleep(0.1)
                    Settings.sendCMD(Settings.lighting_addr, "3~")
                on_stat = True
            if not Settings.cycle_running:
                break


class Snap(QThread):

    transmit = pyqtSignal()

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self._running = False

    def run(self):
        try:
            if Settings.IR_imaging:
                Commands.IR_Imaging_trigger()

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ip_address = "10.0.5.1"
            server_address = (ip_address, 23456)
            sock.connect(server_address)
            cmd = "A~" + str(350) + "~" + str(350) + "~" + \
                str(Settings.rotation) + "~" + str(int(Settings.AOI_X * 100)) + "~" + \
                str(int(Settings.AOI_Y * 100)) + "~" + str(int(Settings.AOI_W * 100)) + \
                "~" + str(int(Settings.AOI_H * 100)) + "~1"
            sock.sendall(cmd.encode())

            with open('../_temp/snapshot.jpg', 'wb') as f:
                while True:
                    data = sock.recv(5)
                    if not data:
                        break
                    f.write(data)
                    self.transmit.emit()
            sock.close()
        except Exception as e:
            print(e)


class Preview(QThread):
    transmit = pyqtSignal()

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self._running = False

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ip_address = "10.0.5.1"
        server_address = (ip_address, 23456)
        sock.connect(server_address)
        cmd = "A~" + str(Settings.x_resolution) + "~" + str(Settings.y_resolution) + "~" + \
            str(Settings.rotation) + "~" + str(int(Settings.AOI_X * 100)) + "~" + \
            str(int(Settings.AOI_Y * 100)) + "~" + str(int(Settings.AOI_W * 100)) + \
            "~" + str(int(Settings.AOI_H * 100)) + \
            "~" + str(int(Settings.imaging_mode))

        start_time = timeit.default_timer()
        sock.sendall(cmd.encode())

        if Settings.imaging_mode == 1:
            with open('../_temp/preview.jpg', 'wb') as f:
                while True:
                    data = sock.recv(5)
                    if not data:
                        break
                    f.write(data)
                    self.transmit.emit()
            sock.close()

        else:
            with open('../_temp/preview.png', 'wb') as f:
                while True:
                    data = sock.recv(5)
                    if not data:
                        break
                    f.write(data)
                    self.transmit.emit()
            sock.close()
        Settings.time_elipsed = int(timeit.default_timer() - start_time)


class Sensor(QThread):
    update = pyqtSignal()
    logstart = pyqtSignal()
    logdone = pyqtSignal()

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self._running = False

    def run(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        time.sleep(1)
        if Settings.acc_attached:
            sensor = adafruit_mma8451.MMA8451(i2c)
        if Settings.temp_attached:
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, 0x76)

        while True:
            try:
                if Settings.tag_index == 0 and Settings.acc_attached:
                    accel_x, accel_y, accel_z = sensor.acceleration
                    Settings.ACC_X_text = "{0:.2f}".format(accel_x)
                    Settings.ACC_Y_text = "{0:.2f}".format(accel_y)
                    Settings.ACC_Z_text = "{0:.2f}".format(accel_z)
                elif Settings.temp_attached:
                    Settings.TEMP_text = "{0:.2f}".format(bme280.temperature)
                    Settings.HUD_text = "{0:.2f}".format(bme280.humidity)
                    Settings.PR_text = "{0:.2f}".format(bme280.pressure)

                self.update.emit()
                sleep(Settings.sample_time)

                if Settings.log_sensor:
                    if not Settings.sensor_flag:
                        self.logstart.emit()
                        if not os.path.isdir(Settings.prelog_dir):
                            os.umask(0)
                            os.mkdir(Settings.prelog_dir)
                        if not os.path.isdir(Settings.log_dir):
                            os.umask(0)
                            os.mkdir(Settings.log_dir)
                        log_file = open(Settings.log_dir + "/log.txt", "w")
                        Settings.sensor_flag = True
                        os.chmod(Settings.log_dir + "/log.txt", 0o777)

                    if Settings.tag_index == 0:

                        log_file.write(Settings.ACC_X_text + "\t" +
                                       Settings.ACC_Y_text + "\t" + Settings.ACC_Z_text + "\r\n")
                    else:

                        log_file.write(Settings.TEMP_text + "\t" +
                                       Settings.HUD_text + "\t" + Settings.PR_text + "\r\n")

                    print(int(timeit.default_timer() - Settings.log_start_time))
                    if int(timeit.default_timer() - Settings.log_start_time > Settings.log_duration):
                        Settings.log_sensor = False
                        Settings.sensor_flag = False
                        log_file.close()
                        self.logdone.emit()
            except Exception as e:
                print(e)


class Timelapse(QThread):
    captured = pyqtSignal()
    transmit = pyqtSignal()
    transmitstart = pyqtSignal()

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self._running = False

    def run(self):
        try:
            if not os.path.isdir(Settings.full_dir):
                os.umask(0)
                os.mkdir(Settings.full_dir)

            for i in range(Settings.total):
                start_time = timeit.default_timer()
                Settings.current = i
                if Settings.imaging_mode == 1:
                    Settings.current_image = Settings.full_dir + \
                        "/" + Settings.sequence_name + "_%04d.jpg" % i
                else:
                    Settings.current_image = Settings.full_dir + \
                        "/" + Settings.sequence_name + "_%04d.png" % i

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(20)
                ip_address = "10.0.5.1"
                server_address = (ip_address, 23456)
                sock.connect(server_address)

                cmd = "A~" + str(Settings.x_resolution) + "~" + str(Settings.y_resolution) + "~" + \
                    str(Settings.rotation) + "~" + str(int(Settings.AOI_X * 100)) + "~" + \
                    str(int(Settings.AOI_Y * 100)) + "~" + str(int(Settings.AOI_W * 100)) + \
                    "~" + str(int(Settings.AOI_H * 100)) + \
                    "~" + str(int(Settings.imaging_mode))

                sock.sendall(cmd.encode())

                with open(Settings.current_image, 'wb') as f:
                    self.transmitstart.emit()
                    while True:
                        try:
                            data = sock.recv(5)
                        except Exception as e:
                            print(e, ': no connections after 5 seconds...')
                            break
                        if not data:
                            break
                        f.write(data)
                        self.transmit.emit()

                sock.close()

                self.captured.emit()
                elapsed = int(timeit.default_timer() - start_time)

                if elapsed < Settings.interval * 60:
                    for x in range(Settings.interval * 60 - elapsed):
                        sleep(1)
                        if not Settings.timelapse_running:
                            break
                if not Settings.timelapse_running:
                    break
        except Exception as e:
            print(e)
            print("general")
