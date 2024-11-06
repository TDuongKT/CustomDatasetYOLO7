import math
import telnetlib
import cv2
import numpy as np
import json
import imutils
import os
import socket
import smbclient.shutil
import time
import logging
import socket

from ftplib import FTP
from yoloDet import YoloTRT
from datetime import datetime, date


client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host_ip = "192.168.3.47"  # PLCのIPアドレス
host_port = 8501
count = 0

model = YoloTRT(library="yolov7/build/libmyplugins.so", engine="yolov7/build/best-yolov7-tiny.engine", conf=0.25, yolo_ver="v7")

# cwd = "/media/jetson-nano/48C9-C4CB"
cwd2 = "smb://192.168.3.200/share"
cwd = os.getcwd()

# config for Cognex camera
ip = "192.168.3.53"
user = 'admin'
password = '123456'

# check if is on detect or wait for detect
check = False
# check to take only 1 picture when detected to waiting to save if it wrong
check_2 = False
results_ok = 0
results_wrong = 0

# Set up the timer variables
pTime = 0
prev_time = 0
start_time = time.time()
interval = 1

count_OK = 0
count_NG = 0

current_date = date.today()
previous_date = date.today()


def network_share_auth():
    smbclient.shutil.copyfile(
    f'{cwd}/DataStorage/check.txt', # Eg - /mnt/myfolder/Test.txt
    '\\\\192.168.3.200\\share\\Jeson-nano\\CheckRun\\check.txt', # Eg \\CDTPS\Test.txt
    username='HDPL', # Username of the the user who have access to the Network drive
    password='Hondapluskt2021') # Password of the the user who have access to the Network drive

def Send_Image_NG():
    smbclient.shutil.copyfile(
    f'{cwd}/DataStorage/tmp_image.jpg', # Eg - /mnt/myfolder/Test.txt
    '\\\\192.168.3.200\\share\\Jeson-nano\\CheckRun\\image.jpg', # Eg \\CDTPS\Test.txt
    username='HDPL', # Username of the the user who have access to the Network drive
    password='Hondapluskt2021') # Password of the the user who have access to the Network drive
    # print(f'{cwd3}/DataStorage/tmp_image.jpg')

def connect(host, port):
    try:
        # クライアント接続
        print(f"{host} {port}")
        client.connect((host, port))  # サーバーに接続(kv-7500にTCP接続/上位リンク通信)
        print("PLC Connected")
    except Exception:
        print("PLC接続NG")
        return "PLC接続NG"
    return "Connected"


def disconnect():
    client.shutdown(socket.SHUT_RDWR)
    client.close()


def send_data_to_plc(device_type, device_no, data_format, data):
    command = f"WR {device_type}{device_no}{data_format} {data}\r"
    print(command)
    try:
        client.send(command.encode("ascii"))
        # print("send : " + str(command.encode("ascii")))
        response = client.recv(32)  # 受信用バイト配列を定義しておく(responseのバイト数以上を設定しておく)
        # print(response)
        response = response.decode("UTF-8")  # PLCからの返答がbyteデータなのでUTF-8にデコード
        if response in "OK":
            print("OK")
        elif response in "E0":
            print(response)
            print("E0 Device No. Error")
        elif response in "E1":
            print(response)
            print("E1 Command Error")
        elif response in "E4":
            print(response)
            print("E4 Write Protected")
        return response
    except Exception as ex:
        print(ex)
        return "Error"


def read_data_from_plc(device_type, device_no, data_format, data_send):
    command = f"RDS {device_type}{device_no}{data_format} {data_send}\r"
    print(command)
    try:
        client.send(command.encode("ascii"))
        # print("send : " + str(command.encode("ascii")))
        response = client.recv(32)  # 受信用バイト配列を定義しておく(responseのバイト数以上を設定しておく)
        # print(response)
        response = response.decode("UTF-8")  # PLCからの返答がbyteデータなのでUTF-8にデコード
        if response in "E0":
            print(response)
            print("E0 Device No. Error")
        elif response in "E1":
            print(response)
            print("E1 Command Error")
        else:
            print("Response :", response)
        return response
    except Exception as ex:
        print(ex)
        return "Error"


def checkNextDay(directory):
    global count_OK
    global count_NG

    global current_date
    global previous_date

    # Get the current date and time
    current_date = date.today()

    # print( f"{current_date}" + "=============" + f"{previous_date}" )
    # Check if the current time is past midnight
    if current_date > previous_date:

        f = open(f"{directory2}/{previous_date}/log.txt", "a")
        f.write(f"NG = {count_NG} \nOK = {count_OK} \n")
        f.close()

        count_OK = 0
        count_NG = 0

    previous_date = current_date


# a là append, w là overwrite
# f = open("ErrorBottle.txt", "a")


def calculate_distance(x1, y1, x2, y2):
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return distance


def get_line_center(x1, y1, x2, y2):
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    return int(center_x), int(center_y)

# Initial distance thresholds
dist_front_threshold = 160
dist_back_threshold = 100
dist_back2_threshold = 180

# Function to update the trackbar value
def update_front_threshold(val):
    global dist_front_threshold
    dist_front_threshold = val

def update_back_threshold(val):
    global dist_back_threshold
    dist_back_threshold = val

def update_back2_threshold(val):
    global dist_back2_threshold
    dist_back2_threshold = val

cv2.namedWindow("Parameters", cv2.WINDOW_AUTOSIZE)
cv2.resizeWindow("Parameters", 300, 150)
cv2.createTrackbar("Front Threshold", "Parameters", dist_front_threshold, 500, update_front_threshold)
cv2.createTrackbar("Back Threshold", "Parameters", dist_back_threshold, 500, update_back_threshold)
cv2.createTrackbar("Back2 Threshold", "Parameters", dist_back2_threshold, 500, update_back2_threshold)

connect(host_ip, host_port)

while True:
    try:
        tn = telnetlib.Telnet(ip)
        tn.read_until(b"User: ")
        tn.write(user.encode('ascii') + b"\r\n")

        tn.read_until(b"Password: ")
        tn.write(password.encode('ascii') + b"\r\n")

        response = tn.read_until(b"\r\n")

        ftp = FTP(ip)
        ftp.login(user, password)
        
        current_datetime = datetime.now()
        today = current_datetime.strftime("%Y-%m-%d")
        month = current_datetime.strftime("%B")
        year = current_datetime.year
        current_time = current_datetime.strftime("%H-%M-%S")

        # dùng lệnh này để trigger chụp ảnh liên tục
        tn.write(b"SE8\r\n")
        # response = tn.read_until(b"\n")
        filename = 'image.bmp'
        rename = 'image_get.bmp'
        lf = open(rename, "wb")
        ftp.retrbinary("RETR " + filename, lf.write)
        lf.close()
        image = cv2.imread(rename)

        curr_time = time.time()
        elapsed_time = curr_time - prev_time

        #if elapsed_time > interval:   
        f = open(f"{cwd}/DataStorage/check.txt", "w")
        f.write(f"Send at: {current_datetime}")
        f.close()

        #network_share_auth()
        # Send_Image_NG()

        prev_time = curr_time

        bottleneck = []
        front = []
        back = []
        back2 = []
        back3 = []

        count = 0
        message = "Waiting To Detect....."

        frame = imutils.resize(image, width=1200)
        frame = frame[300:1200, 250:800]
        # frame_2 = imutils.resize(frame, width=800)
        # roi = frame_2[0:800, 0:700]

        detections, t = model.Inference(frame)
        # for obj in detections:
        #  print(obj['class'], obj['conf'], obj['box'])

        check_bottleneck = True
        check_front = True
        check_back = True
        check_back2 = True
        check_back3 = True

        check_has_bottleneck = 0

        for obj in detections:
            # kiểm tra tên cửa vật thể dectect
            name = obj['class']
            # print(name)
            if name == "bottleneck":
                bottleneck.append(obj['box'][0])
                bottleneck.append(obj['box'][1])
                bottleneck.append(obj['box'][2])
                bottleneck.append(obj['box'][3])
                check_has_bottleneck = 1
                count += 1
            elif name == "front" and check_front:
                front.append(obj['box'][0])
                front.append(obj['box'][1])
                front.append(obj['box'][2])
                front.append(obj['box'][3])
                count += 1
            elif name == "back" and check_back:
                back.append(obj['box'][0])
                back.append(obj['box'][1])
                back.append(obj['box'][2])
                back.append(obj['box'][3])
                count += 1
            elif name == "back_2" and check_back2:
                back2.append(obj['box'][0])
                back2.append(obj['box'][1])
                back2.append(obj['box'][2])
                back2.append(obj['box'][3])
                count += 1
            elif name == "back_2" and check_back2:
                back3.append(obj['box'][0])
                back3.append(obj['box'][1])
                back3.append(obj['box'][2])
                back3.append(obj['box'][3])
                count += 1

        # print(bottleneck)
        # print(back)
        # print(back2)
        # print(front)

        # Finding distance between people
        dist_neck_to_back = 0
        dist_neck_to_front = 0
        dist_neck_to_back2 = 0
        dist_neck_to_back3 = 0


        center_y2 = 0

        if check_has_bottleneck > 0 and count > 1:
            if len(bottleneck) > 0 and len(front) > 0:
                centroid_bottleneck = (int(bottleneck[0] + (bottleneck[2] / 2)), int(bottleneck[1] + (bottleneck[3] / 2)))
                centroid_front = (int(front[0] + (front[2] / 2)), int(front[1] + (front[3] / 2)))

                center_x1, center_y1 = get_line_center(int(front[0]), int(front[1]), int(front[2]), int(front[3]))
                center_x2, center_y2 = get_line_center(int(bottleneck[0]), int(bottleneck[1]), int(bottleneck[2]), int(bottleneck[3]))
                dist_neck_to_front = calculate_distance(center_x2, center_y1, center_x2, center_y2)

                cv2.putText(frame, "Front : " + str(dist_neck_to_front), (0, 250), cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 255), 3)         
                cv2.line(frame, (center_x2, center_y1), (center_x2, center_y2), (0, 0, 255), 2)
            elif len(bottleneck) > 0 and len(back) > 0:
                centroid_bottleneck = (int(bottleneck[0] + (bottleneck[2] / 2)), int(bottleneck[1] + (bottleneck[3] / 2)))
                centroid_back = (int(back[0] + (back[2] / 2)), int(back[1] + (back[3] / 2)))

                center_x1, center_y1 = get_line_center(int(back[0]), int(back[1]), int(back[2]), int(back[3]))
                center_x2, center_y2 = get_line_center(int(bottleneck[0]), int(bottleneck[1]), int(bottleneck[2]), int(bottleneck[3]))
                dist_neck_to_back = calculate_distance(center_x2, center_y1, center_x2, center_y2)
                
                cv2.putText(frame, "Back : " + str(dist_neck_to_back), (0, 250), cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 255), 3)      
                cv2.line(frame, (center_x2, center_y1), (center_x2, center_y2), (0, 0, 255), 2)

            elif len(bottleneck) > 0 and len(back2) > 0:
                centroid_bottleneck = (int(bottleneck[0] + (bottleneck[2] / 2)), int(bottleneck[1] + (bottleneck[3] / 2)))
                centroid_back2 = (int(back2[0] + (back2[2] / 2)), int(back2[1] + (back2[3] / 2)))

                center_x1, center_y1 = get_line_center(int(back2[0]), int(back2[1]), int(back2[2]), int(back2[3]))
                center_x2, center_y2 = get_line_center(int(bottleneck[0]), int(bottleneck[1]), int(bottleneck[2]), int(bottleneck[3]))

                dist_neck_to_back2 = calculate_distance(center_x2, center_y1, center_x2, center_y2)

                cv2.putText(frame, "Back_2 : " + str(dist_neck_to_back2), (0, 250), cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 255), 3)
                cv2.line(frame, (center_x2, center_y1), (center_x2, center_y2), (0, 0, 255), 2)
            elif len(bottleneck) > 0 and len(back3) > 0:
                centroid_bottleneck = (int(bottleneck[0] + (bottleneck[2] / 2)), int(bottleneck[1] + (bottleneck[3] / 2)))
                centroid_back2 = (int(back3[0] + (back3[2] / 2)), int(back3[1] + (back3[3] / 2)))

                center_x1, center_y1 = get_line_center(int(back3[0]), int(back3[1]), int(back3[2]), int(back3[3]))
                center_x2, center_y2 = get_line_center(int(bottleneck[0]), int(bottleneck[1]), int(bottleneck[2]), int(bottleneck[3]))

                dist_neck_to_back3 = calculate_distance(center_x2, center_y1, center_x2, center_y2)

                cv2.putText(frame, "Back_3 : " + str(dist_neck_to_back3), (0, 250), cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 255), 3)
                cv2.line(frame, (center_x2, center_y1), (center_x2, center_y2), (0, 0, 255), 2)
            else:
                message = "Can not detect"

        # khi khoảng cách từ vật thể nằm sau nằm gần cổ chai thì tức la nhãn bị ngược
        # ngược lại thì khi khoảng cách từ vật thể phía trước so với cổ chai bị xa thì túc là nhãn dán cũng không đúng

        if dist_neck_to_front > dist_front_threshold:
            message = "Wrong"
        elif 0 < dist_neck_to_front < dist_front_threshold:
            message = "OK"
        elif dist_neck_to_back > dist_back_threshold:
            message = "OK"
        elif 0 < dist_neck_to_back < dist_back_threshold:
            message = "Wrong"
        elif dist_neck_to_back2 > dist_back2_threshold:
            message = "Wrong"
        elif 0 < dist_neck_to_back2 < dist_back2_threshold:
            message = "OK"
        elif dist_neck_to_back3 > dist_back_threshold:
            message = "OK"
        elif 0 < dist_neck_to_back3 < dist_back_threshold:
            message = "Wrong"
        else:
            message = "Waiting To Detect....."

        #if dist_neck_to_front > 160:
         #   message = "Wrong"
        #elif 0 < dist_neck_to_front < 160:
           #   message = "OK"
      #      #elif dist_neck_to_back > 100:
         #      # message = "OK"
          #elif 0 < dist_neck_to_back < 100:
             # message = "Wrong"
          #elif dist_neck_to_back2 > 180:
             # message = "Wrong"
          #elif 0 < dist_neck_to_back2 < 180:
             # errorImage = cv2.imread(f"{cwd}/DataStorage/tmp_image.jpg")
            #  message = "OK"
          #else:
             # message = "Waiting To Detect....."

        # checking time
        curr_time = time.time()
        elapsed_time = curr_time - prev_time

        directory1 = cwd + f"/DataStorage/{str(year)}"
        directory2 = cwd + f"/DataStorage/{str(year)}/{str(month)}"
        directory3 = cwd + f"/DataStorage/{str(year)}/{str(month)}/{str(today)}"
        directory4 = cwd + f"/DataStorage/{str(year)}/{str(month)}/{str(today)}/ImageError"

        if not os.path.isdir(directory1):
            os.mkdir(directory1)
        if not os.path.isdir(directory2):
            os.mkdir(directory2)
        if not os.path.isdir(directory3):
            os.mkdir(directory3)
            open(f"{directory3}/Distance.txt", "x")
            open(f"{directory3}/log.txt", "x")
        if not os.path.isdir(directory4):
            os.mkdir(directory4)


        #checkNextDay(directory2)

        # Calculate all result in the list to determine that the film is wrong or Ok
        if message == "Waiting To Detect.....":
            # if elapsed_time > interval:
            if results_wrong > results_ok and results_wrong >= 4:
                try:
                    errorImage = cv2.imread(f"{cwd}/DataStorage/tmp_image.jpg")
                    cv2.imwrite(f"{directory4}/NG-{current_time}.jpg", errorImage)
                    count_NG += 1
                    #Send_Image_NG()
                    
                    #send_data_to_plc("DM", "9000", ".S", 1)

                    #send_data_to_plc("DM", "9002", ".S", f"{count_NG}")
                    
                except Exception as e:
                    print(e)
            elif results_ok > results_wrong and results_ok >= 3:
                count_OK += 1
                #send_data_to_plc("DM", "9006", ".S", f"{count_OK}")

                #send_data_to_plc("DM", "9000", ".S", 0)

            count += 1
            prev_time = curr_time
            check = False
            check_2 = True
            results_ok = 0
            results_wrong = 0
        else:
            check = True


        # Start counting to check when film is detect is wrong or not
        # print(message)
        if check:    
            if message == "OK":
                results_ok += 1
            else:
                results_wrong += 1
                if check_2:
                    cv2.imwrite(f"{cwd}/DataStorage/tmp_image.jpg", image)
                    if results_wrong > results_ok and results_wrong >= 3: 
                        #errorImage = cv2.imread(f"{cwd}/DataStorage/tmp_image.jpg")
                        if dist_neck_to_front > 0:
                            f = open(f"{directory3}/Distance.txt", "a")
                            f.write(f"NG in front at {current_time} -- distance: {dist_neck_to_front} \n")
                            f.close()
                            # cv2.imwrite(f"{directory4}/NG-{current_time}.jpg", errorImage)
                        elif dist_neck_to_back > 0:
                            f = open(f"{directory3}/Distance.txt", "a")
                            f.write(f"NG in back at {current_time} -- distance: {dist_neck_to_back} \n")
                            f.close()
                            # cv2.imwrite(f"{directory4}/NG-{current_time}.jpg", errorImage)
                        elif dist_neck_to_back2 > 0:
                            f = open(f"{directory3}/Distance.txt", "a")
                            f.write(f"NG in back2 at {current_time} -- distance: {dist_neck_to_back2} \n")
                            f.close()
                            # cv2.imwrite(f"{directory4}/NG-{current_time}.jpg", errorImage)
                        elif dist_neck_to_back2 > 0:
                            f = open(f"{directory3}/Distance.txt", "a")
                            f.write(f"NG in back2 at {current_time} -- distance: {dist_neck_to_back2} \n")
                            f.close()
                        check_2 = False


        # print(message)

        fps = 1 / (curr_time - pTime)  # tính fps (Frames Per Second) - đây là chỉ số khung hình trên mỗi giây
        pTime = curr_time

        # print("FPS: {} sec".format(1/t))
        # cv2.putText(frame, "FPS: {} sec".format(1/t), (0, 50), cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 0), 3)

        cv2.putText(frame, f"FPS: {int(fps)}", (0, 50), cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 0), 3)
        cv2.putText(frame, message, (0, 100), cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 0), 3)
        cv2.putText(frame, "Ok: " + str(results_ok), (0, 159), cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 0), 3)
        cv2.putText(frame, "NG: " + str(results_wrong), (0, 200), cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 255), 3)
        cv2.imshow("Result", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    except Exception as e:
       print(e)

cv2.destroyAllWindows()