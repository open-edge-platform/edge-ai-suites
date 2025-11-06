"""
Test script for VideoAnalyticsPipelineService
"""

from components.va import VideoAnalyticsPipelineService
import time
import sys


def example_single_pipeline():
    """Launch a single pipeline"""
    print("=== Single Pipeline Example ===\n")

    # Create service
    service = VideoAnalyticsPipelineService()

    try:
        # Launch front camera pipeline
        print("Launching 'front' pipeline...")

        if service.launch_pipeline(
            pipeline_name="front", source="rtsp://127.0.0.1:8554/front"
        ):
            print("✓ Pipeline launched successfully\n")

            # Get status for a while
            print("Monitoring pipeline status for 10 seconds...")
            for i in range(60):
                status = service.get_pipeline_status("front")
                if status:
                    print(
                        f"[{i+1}] Running: {status['running']}, PID: {status['pid']}",
                        end="",
                    )
                    if "cpu_percent" in status:
                        print(
                            f", CPU: {status['cpu_percent']:.1f}%, Memory: {status['memory_mb']:.1f} MB"
                        )
                    else:
                        print()
                time.sleep(1)
        else:
            print("✗ Failed to launch pipeline")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        print("\nStopping pipeline...")
        service.stop_pipeline("front")
        print("Done")


def example_multiple_pipelines():
    """Launch all 3 pipelines and monitor content pipeline output"""
    print("=== Multiple Pipelines Example ===\n")

    service = VideoAnalyticsPipelineService()

    try:
        # Launch front camera
        print("Launching 'front' pipeline...")
        service.launch_pipeline(
            pipeline_name="front", source="rtsp://127.0.0.1:8554/front"
        )
        time.sleep(2)

        # Launch back camera
        print("Launching 'back' pipeline...")
        service.launch_pipeline(
            pipeline_name="back", source="rtsp://127.0.0.1:8554/back"
        )
        time.sleep(2)

        # Launch content pipeline
        print("Launching 'content' pipeline...")
        service.launch_pipeline(
            pipeline_name="content", source="rtsp://127.0.0.1:8554/content"
        )
        time.sleep(2)

        # Show status of all pipelines
        print("\n--- All Pipelines Status ---")
        all_status = service.get_all_pipelines_status()
        for name, status in all_status.items():
            if status:
                print(f"\n{name.upper()}:")
                print(f"  Running: {status['running']}")
                print(f"  PID: {status['pid']}")
                print(f"  Log file: {status.get('log_file', 'N/A')}")
                print(f"  Output files: {status.get('output_files', [])}")

        # Monitor content pipeline output (first 20 JSON objects)
        print("\n--- Monitoring Content Pipeline Output ---")
        print("Reading first 20 JSON objects from content_results.txt...\n")

        count = 0
        for json_obj in service.monitor_pipeline("content", "content_results.txt"):
            count += 1
            print(f"[{count}] Frame: {json_obj.get('frame', {}).get('number', 'N/A')}")

            print(json_obj["objects"][0]["classification_layer_name:output"])
            if count >= 20:
                print("\n(Stopping after 20 objects)")
                break

        time.sleep(120)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        print("\nStopping all pipelines...")
        service.stop_all_pipelines()
        print("Done")


def main():
    """Main entry point"""
    examples = {
        "single": example_single_pipeline,
        "multiple": example_multiple_pipelines,
    }

    if len(sys.argv) > 1:
        example_name = sys.argv[1]

        if example_name in examples:
            examples[example_name]()
        else:
            print(f"Unknown example: {example_name}")
            print(f"Available examples: {', '.join(examples.keys())}")
    else:
        # Show menu
        print("VideoAnalyticsPipelineService Test Examples\n")
        print("Available examples:")
        print("  single     - Launch a single pipeline and monitor status")
        print("  multiple   - Launch all 3 pipelines and monitor content output")
        print("\nUsage: python test_va_pipeline_service.py <example>")


if __name__ == "__main__":
    main()
