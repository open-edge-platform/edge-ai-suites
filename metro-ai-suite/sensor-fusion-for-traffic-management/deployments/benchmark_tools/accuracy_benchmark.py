import numpy as np
import pickle
import cv2
import os
import csv
import argparse

### plot gt and detection results in same image

## compare the distance of center point
def compare_center_distance(detections, gts):
    num_frame = len(detections)

    errors_percentages =[]

    for i in range(num_frame):
        frame_detection = detections[i]
        frame_gt = gts[i]

        print("frameId: ", frame_detection['frameId'])
        print("detections: ", frame_detection['detections'])
        print("gts: ", frame_gt['gts'])


        # find gt for each detection and compute the nearst distance
        
        for detection in frame_detection['detections']:
            radar_cx = detection['radar_cx']
            radar_cy = detection['radar_cy']
            group = detection['group']

            distances =[]

            ## remove useless frame_detection
            if radar_cx == 0.0 and radar_cy == 0.0:
                continue

            for gt in frame_gt['gts']:
                gt_cx = gt['gt_xc']
                gt_cy = gt['gt_yc']

                ## change gt , radar to same coordinates
                temp = gt_cx
                gt_cx = gt_cy
                gt_cy= -temp
                gt_group = gt['group']
                
                # compute the distance of nearest gt if exsit

                distance = np.sqrt((radar_cx - gt_cx) ** 2 + (radar_cy - gt_cy) ** 2)
                distances.append(distance)
                print("frameId: ", i, "group: ", group, "gt_group: ", gt_group, "radar_cx: ", radar_cx, "radar_cy: ", radar_cy, "gt_cx: ", gt_cx, "gt_cy: ", gt_cy, "distance: ", distance)
            
            # find the nearest distance for each detection
            min_dist_detction = min(distances)
            print('**distance for detection**: ', "frameId: ", i, "radar_cx: ", radar_cx, "radar_cy: ", radar_cy, "min dist: ", min_dist_detction)
            
            error_percentage = min_dist_detction / (np.sqrt(radar_cx**2+radar_cy**2)) *100
            print('error_percentage: ', error_percentage)

            if error_percentage < 20:
                errors_percentages.append(error_percentage)
    
    average_error = np.mean(errors_percentages)
    print('average error: ', average_error)


            

        


def accuracy_benchmark(img_dir, output_dir, gt_file_path, tracking_file_path):
    # read tracking csv files 

    frame_detections = []  # save radar detection results(tracking results)
    frame_gts = [] # save gt results

    with open(tracking_file_path, mode='r') as detection_file:
        tracking_csv_reader = csv.reader(detection_file)

        # skip the header
        next(tracking_csv_reader)
        for row in tracking_csv_reader:
            print(row)
            frameId = row[0]
            radarRois = row[1]
            radarSizes = row[2]
            radarStates = row[3]
            radarId = row[4]

            # Clean and split the radarRois and radarSizes strings
            parts = radarRois.split()
            radarSize = radarSizes.split()

            if len(parts) % 4 == 0:
                num_groups = len(parts) // 4
                frame_data = {
                    'frameId': frameId,
                    'detections': []
                }
                for i in range(num_groups):
                    try:
                        # radar_x, radar_y actually is the center coordinates of the radar box
                        radar_x, radar_y, vx, vy = map(float, parts[i*4:(i+1)*4])
                        w, h = map(float, radarSize[i*2:(i+1)*2])

                        # align with garnet park demo
                        radar_y = -radar_y  # for plot
                        xSize = 4.2
                        ySize = 1.7

                        radar_x1 = radar_x + xSize / 2
                        radar_y1 = radar_y - ySize / 2

                        radar_x2 = radar_x - xSize / 2
                        radar_y2 = radar_y + ySize / 2
                        detection = {
                            'group': i + 1,
                            'radar_x1': radar_x1,
                            'radar_y1': radar_y1,
                            'radar_x2': radar_x2,
                            'radar_y2': radar_y2,
                            'radar_cx': radar_x,
                            'radar_cy': radar_y
                        }

                        frame_data['detections'].append(detection)
                        print("boxes left: ", (radar_x1, radar_y1), "boxes right: ", (radar_x2, radar_y2))
                    except ValueError as e:
                        print(f"Error converting to float: {e}")
                        print(f"Problematic data: {parts[i*4:(i+1)*4]}")
                frame_detections.append(frame_data)
            else:
                print(f"Invalid number of coordinates in radarRois: {radarRois}")

    
    with open(gt_file_path, mode='r') as gt_file:
        gt_csv_reader = csv.reader(gt_file)

        # skip the header
        next(gt_csv_reader)
        for row in gt_csv_reader:
            print(row)
            frameId = row[0]
            radar_rois = row[1]
            class_labels = row[2]

            # Clean and split the radar_rois string
            radar_rois_cleaned = radar_rois.replace('[', '').replace(']', '').replace(',', ' ')
            parts_gt = radar_rois_cleaned.split()
            # parts_gt = radar_rois.split()
            labels_gt = class_labels.split()

            if len(parts_gt) % 6 == 0:
                num_groups_gt = len(parts_gt) // 6
                frame_data = {
                    'frameId': frameId,
                    'gts': []
                }
                for i in range(num_groups_gt):
                    try:
                        gt_x1, gt_y1, gt_x2, gt_y2, gt_xc, gt_yc = map(float, parts_gt[i*6:(i+1)*6])
                        ## compute center point of bounding box

                        gt = {
                            'group': i + 1,
                            'gt_x1': gt_x1,
                            'gt_y1': gt_y1,
                            'gt_x2': gt_x2,
                            'gt_y2': gt_y2,
                            'gt_xc': gt_xc,
                            'gt_yc': gt_yc
                        }
                        frame_data['gts'].append(gt)
                        print("gt boxes left: ", (gt_x1, gt_y1), "gt boxes right: ", (gt_x2, gt_y2))
                    except ValueError as e:
                        print(f"Error converting to float: {e}")
                        print(f"Problematic data: {parts_gt[i*4:(i+1)*4]}")
                frame_gts.append(frame_data)
            else:
                print(f"Invalid number of coordinates in radar_rois: {radar_rois}")    


        print('len detections: ', len(frame_detections))
        print('len gts: ', len(frame_gts))

        compare_center_distance(frame_detections, frame_gts)






        



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read radar gt and detection results and compute accuracy")
    parser.add_argument("--folder_path", required=True, type=str, help="Path to the gt and tracking results")
    
    args = parser.parse_args()
    folder_path = args.folder_path

    ### params
    ## birdview shape
    resolution = 100/512
    width = 512
    height = 256

    ## original image shape
    ori_img_width = 640
    ori_img_height = 480

    ## origin coordinates
    x_min = 0.0
    x_min_pixel = x_min/resolution
    origin_row = int(height + x_min_pixel)
    origin_col = int(width/2)
    print("origin_row: ", origin_row)
    print("origin_col: ", origin_col)

    # Define the directories containing the ground truth and images
    gt_dir = os.path.join(folder_path, "gt")
    img_dir = os.path.join(folder_path, "left")
    output_dir = os.path.join(folder_path, "gt_images") # new directory for saving gt images

    # Create the output directory if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # CSV file setup
    gt_file_path = os.path.join(folder_path, 'radar_gt.csv')
    tracking_file_path = os.path.join(folder_path, 'radarResults.csv')

    accuracy_benchmark(img_dir, output_dir, gt_file_path, tracking_file_path)
