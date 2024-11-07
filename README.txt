Cac buoc de train model YOLOv7:

1.	Tạo môi trường mới
2.	install library:
			Truy cập vào 'https://pytorch.org' tải torch tương thích với cuda ( check cuda: nvidia-smi ) 
			pip install -r requirments.txt
3.	clone repo: git clone http://192.168.1.8:40804/tduongkt/trainning_yolov7
4.	download, set up data theo form ( yolov8 format) của roboflow
5.	lệnh train model:
	python tranning_yolov7/train.py --batch 50 --cfg tranning_yolov7/cfg/training/Custom-yolov7-tiny.yaml --epochs 100 --data tranning_yolov7/data/data.yaml --weights 'tranning_yolov7/yolov7-tiny.pt'
