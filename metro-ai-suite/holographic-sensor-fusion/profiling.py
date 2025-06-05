import json
import matplotlib.pyplot as plt
import argparse

def main(json_file):
    latencies = []

    # read json file
    with open(json_file) as f:
        json_data = json.load(f)

    frame_latencies = []

    for frame in json_data["TimeStamps"]:
        time_stamps = {ts["name"]: int(ts["timeStamp"]) for ts in frame["TimeStamp"]}
        latencies = {}

        if "decodeIn" in time_stamps and "decodeOut" in time_stamps:
            latencies["decode"] = time_stamps["decodeOut"] - time_stamps["decodeIn"]
        if "detectionIn" in time_stamps and "detectionOut" in time_stamps:
            latencies["detection"] = time_stamps["detectionOut"] - time_stamps["detectionIn"]
        # if "detectionIn" in time_stamps and "inferenceOut" in time_stamps:
        #     latencies["inference"] = time_stamps["inferenceOut"] - time_stamps["detectionIn"]
        if "RadarPreprocessIn" in time_stamps and "RadarPreprocessOut" in time_stamps:
            latencies["RadarPreprocess"] = time_stamps["RadarPreprocessOut"] - time_stamps["RadarPreprocessIn"]
        if "RadarDetectionIn" in time_stamps and "RadarDetectionOut" in time_stamps:
            latencies["RadarDetection"] = time_stamps["RadarDetectionOut"] - time_stamps["RadarDetectionIn"]
        if "RadarClusteringIn" in time_stamps and "RadarClusteringOut" in time_stamps:
            latencies["RadarClustering"] = time_stamps["RadarClusteringOut"] - time_stamps["RadarClusteringIn"]
        if "RadarTrackingIn" in time_stamps and "RadarTrackingOut" in time_stamps:
            latencies["RadarTracking"] = time_stamps["RadarTrackingOut"] - time_stamps["RadarTrackingIn"]    
                                                                                                     
        if "RadarReaderIn" in time_stamps and "RadarReaderOut" in time_stamps:
            latencies["RadarReader"] = time_stamps["RadarReaderOut"] - time_stamps["RadarReaderIn"]
        if "MediaTrackerIn" in time_stamps and "MediaTrackerOut" in time_stamps:
            latencies["MediaTracker"] = time_stamps["MediaTrackerOut"] - time_stamps["MediaTrackerIn"]
        if "coordinateTransIn" in time_stamps and "coordinateTransOut" in time_stamps:
            latencies["coordinateTrans"] = time_stamps["coordinateTransOut"] - time_stamps["coordinateTransIn"]
        if "track2trackIn" in time_stamps and "track2trackOut" in time_stamps:
            latencies["track2track"] = time_stamps["track2trackOut"] - time_stamps["track2trackIn"]
        if "postFusionIn" in time_stamps and "postFusionOut" in time_stamps:
            latencies["postFusion"] = time_stamps["postFusionOut"] - time_stamps["postFusionIn"]
            latencies["e2e"] = time_stamps["postFusionOut"] - time_stamps["decodeIn"]
        ##
        if "postFusion" in latencies and "e2e" in latencies:
            frame_latencies.append(latencies)

    # compute the average latency of each component
    if frame_latencies:
        num_frame = len(frame_latencies)
        # check existence of each key

        decode_avg_latency = round(sum([frame.get("decode", 0) for frame in frame_latencies]) / num_frame, 2)
        detection_avg_latency = round(sum([frame.get("detection", 0) for frame in frame_latencies]) / num_frame, 2)
        # inference_avg_latency = round(sum([frame.get("inference", 0) for frame in frame_latencies]) / num_frame, 2)
        radar_preprocess_avg_latency = round(sum([frame.get("RadarPreprocess", 0) for frame in frame_latencies]) / num_frame, 2)
        radar_detection_avg_latency = round(sum([frame.get("RadarDetection", 0) for frame in frame_latencies]) / num_frame, 2)
        radar_clustering_avg_latency = round(sum([frame.get("RadarClustering", 0) for frame in frame_latencies]) / num_frame, 2)
        radar_tracking_avg_latency = round(sum([frame.get("RadarTracking", 0) for frame in frame_latencies]) / num_frame, 2)
        
        RadarReader_avg_latency = abs(round(sum([frame.get("RadarReader", 0) for frame in frame_latencies]) / num_frame, 2))
        MediaTracker_avg_latency = round(sum([frame.get("MediaTracker", 0) for frame in frame_latencies]) / num_frame, 2)
        coordinateTrans_avg_latency = round(sum([frame.get("coordinateTrans", 0) for frame in frame_latencies]) / num_frame, 2)
        track2track_avg_latency = round(sum([frame.get("track2track", 0) for frame in frame_latencies]) / num_frame, 2)
        postFusion_avg_latency = round(sum([frame.get("postFusion", 0) for frame in frame_latencies]) / num_frame, 2)
        e2e_avg_latency = round(sum([frame.get("e2e", 0) for frame in frame_latencies]) / num_frame, 2)


        print(f"decode_avg_latency: {decode_avg_latency} ms")
        print(f"detection_avg_latency: {detection_avg_latency} ms")
        # print(f"inference_avg_latency: {inference_avg_latency} ms")
        print(f"radar_preprocess_avg_latency: {radar_preprocess_avg_latency} ms")
        print(f"radar_detection_avg_latency: {radar_detection_avg_latency} ms")
        print(f"radar_clustering_avg_latency: {radar_clustering_avg_latency} ms")
        print(f"radar_tracking_avg_latency: {radar_tracking_avg_latency} ms")
        print(f"RadarReader_avg_latency: {RadarReader_avg_latency} ms")
        print(f"MediaTracker_avg_latency: {MediaTracker_avg_latency} ms")
        print(f"coordinateTrans_avg_latency: {coordinateTrans_avg_latency} ms")
        print(f"track2track_avg_latency: {track2track_avg_latency} ms")
        print(f"postFusion_avg_latency: {postFusion_avg_latency} ms")
        print(f"e2e_avg_latency: {e2e_avg_latency} ms")

    if RadarReader_avg_latency == 0.0:
        components = ['decode', 'detection', 'RadarPreprocess', 'RadarDetection','RadarClustering','RadarTracking','MediaTracker', 'coordinateTrans', 'postFusion', 'e2e']
        latencies = [decode_avg_latency, detection_avg_latency, radar_preprocess_avg_latency,radar_detection_avg_latency, radar_clustering_avg_latency, radar_tracking_avg_latency, MediaTracker_avg_latency, coordinateTrans_avg_latency, postFusion_avg_latency, e2e_avg_latency]
    else:
        components = ['decode', 'detection', 'RadarReader', 'MediaTracker', 'coordinateTrans', 'postFusion', 'e2e']
        latencies = [decode_avg_latency, detection_avg_latency, RadarReader_avg_latency, MediaTracker_avg_latency, coordinateTrans_avg_latency, postFusion_avg_latency, e2e_avg_latency]

    plt.figure(figsize=(10, 6))
    plt.bar(components, latencies, color='skyblue')

    plt.xticks(rotation=45)

    # add title and label
    plt.title('Average Latency of Components')
    plt.xlabel('Components')
    plt.ylabel('Latency (ms)')

    # display the value of each bar
    for i, v in enumerate(latencies):
        plt.text(i, v + 0.5, f"{v:.2f} ms", ha='center', color='black')

    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process performance data JSON file.')
    parser.add_argument('json_file', type=str, help='Path to the JSON file containing performance data')
    args = parser.parse_args()
    main(args.json_file)