import cv2
import numpy as np
import math

def create_section_timer(
    sections,
    output_filename="presentation_timer.mp4",
    fps=30,
    fast_render=True,
    fast_output_fps=1,
    render_mode=None,
):
    # Video layout settings for drawing canvas
    width, height = 1920, 1080
    output_width, output_height = width, height

    # Allow section durations to be defined in minutes for easier authoring.
    normalized_sections = []
    for sec in sections:
        if "duration_minutes" in sec:
            duration_seconds = int(round(sec["duration_minutes"] * 60))
        else:
            duration_seconds = int(sec["duration"])
        normalized_sections.append({
            "name": sec["name"],
            "color": sec["color"],
            "duration": max(0, duration_seconds),
        })

    # Optional quality/speed presets.
    # If render_mode is provided, it overrides fps/fast_render/fast_output_fps.
    if render_mode is not None:
        mode = str(render_mode).lower()
        if mode == "ultra_fast":
            fast_render = True
            fast_output_fps = 1
            output_width, output_height = 1280, 720
        elif mode == "balanced":
            fast_render = True
            fast_output_fps = 3
            output_width, output_height = 1600, 900
        elif mode == "final":
            fast_render = False
            output_width, output_height = 1920, 1080
        else:
            raise ValueError(
                "render_mode must be one of: ultra_fast, balanced, final"
            )
    
    # Calculate total timeline properties
    total_seconds = sum(sec["duration"] for sec in normalized_sections)

    # Define codec and video writer (PowerPoint-friendly MP4 format)
    writer_fps = max(1, int(fast_output_fps)) if fast_render else max(1, int(fps))
    total_frames = total_seconds * writer_fps
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_filename, fourcc, writer_fps, (output_width, output_height))
    
    # Font configurations
    font = cv2.FONT_HERSHEY_SIMPLEX
    line_type = cv2.LINE_8 if (render_mode is not None and str(render_mode).lower() == "ultra_fast") else cv2.LINE_AA
    
    # Build section boundaries once for fast lookups and arc construction
    section_ranges = []
    cursor = 0
    for sec in normalized_sections:
        start = cursor
        end = cursor + sec["duration"]
        section_ranges.append({
            "name": sec["name"],
            "color": sec["color"],  # Expecting BGR tuple
            "duration": sec["duration"],
            "start": start,
            "end": end,
        })
        cursor = end
    
    # Fast mode reduces output frame rate to speed up generation significantly.
    # Duration remains correct because total_frames = total_seconds * writer_fps.
    render_steps = total_frames

    print(
        f"Generating presentation timer ({total_seconds} seconds total, "
        f"mode={render_mode}, fast_render={fast_render}, writer_fps={writer_fps}, "
        f"output={output_width}x{output_height})..."
    )

    for frame_idx in range(render_steps):
        is_time_up = frame_idx == (render_steps - 1)
        elapsed_seconds = min(total_seconds, frame_idx / writer_fps)
        overall_remaining = max(0, math.ceil(total_seconds - elapsed_seconds))

        # Resolve current section from boundaries
        current_sec = section_ranges[-1]
        for sec in section_ranges:
            if elapsed_seconds < sec["end"]:
                current_sec = sec
                break

        section_elapsed = min(current_sec["duration"], max(0.0, elapsed_seconds - current_sec["start"]))
        section_remaining = max(0, math.ceil(current_sec["duration"] - section_elapsed))
        section_elapsed_clock = int(math.floor(section_elapsed))
        overall_elapsed_clock = int(math.floor(elapsed_seconds))

        if is_time_up:
            overall_remaining = 0
        overall_time_str = f"{overall_remaining // 60:02d}:{overall_remaining % 60:02d}"
        section_time_str = f"{section_remaining // 60:02d}:{section_remaining % 60:02d}"
        overall_elapsed_str = f"{overall_elapsed_clock // 60:02d}:{overall_elapsed_clock % 60:02d}"
        section_elapsed_str = f"{section_elapsed_clock // 60:02d}:{section_elapsed_clock % 60:02d}"
        
        # Initialize solid black frame
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        show_section_labels = len(section_ranges) > 1

        # Single centered layout focused on overall timer.
        # For a single-section timer, use the section name as the main title.
        title = "OVERALL TIMER" if show_section_labels else current_sec["name"]
        title_scale = 1.7
        title_thickness = 4
        title_size = cv2.getTextSize(title, font, title_scale, title_thickness)[0]
        cv2.putText(
            frame,
            title,
            ((width - title_size[0]) // 2, 120),
            font,
            title_scale,
            (225, 225, 225),
            title_thickness,
            line_type,
        )

        overall_center_x, overall_center_y = width // 2, 560
        overall_radius = 374
        ring_thickness = 40

        # Multicolor overall pie ring: each section occupies its proportional arc
        arc_segments = []
        angle_cursor = -90.0
        for sec in section_ranges:
            span = (sec["duration"] / total_seconds) * 360.0 if total_seconds > 0 else 0.0
            start_angle = angle_cursor
            end_angle = angle_cursor + span
            arc_segments.append({
                "name": sec["name"],
                "color": sec["color"],
                "start_angle": start_angle,
                "end_angle": end_angle,
            })
            cv2.ellipse(
                frame,
                (overall_center_x, overall_center_y),
                (overall_radius, overall_radius),
                0,
                start_angle,
                end_angle,
                sec["color"],
                ring_thickness,
                line_type,
            )
            angle_cursor = end_angle

        if show_section_labels:
            # Place each section label outside the ring with connector lines for readability.
            # Label boxes are clamped within the frame and offset away from the pie chart.
            label_scale = title_scale
            label_thickness = title_thickness
            label_pad_x = 20
            label_pad_y = 14
            label_box_h = 72
            for segment in arc_segments:
                mid_angle = (segment["start_angle"] + segment["end_angle"]) / 2.0
                mid_rad = math.radians(mid_angle)

                anchor_r = overall_radius + ring_thickness // 2
                anchor_x = int(overall_center_x + anchor_r * math.cos(mid_rad))
                anchor_y = int(overall_center_y + anchor_r * math.sin(mid_rad))

                label_r = overall_radius + 120
                center_x = int(overall_center_x + label_r * math.cos(mid_rad))
                center_y = int(overall_center_y + label_r * math.sin(mid_rad))

                text = segment["name"]
                text_size = cv2.getTextSize(text, font, label_scale, label_thickness)[0]
                box_w = text_size[0] + label_pad_x * 2
                box_h = max(label_box_h, text_size[1] + label_pad_y * 2)

                # Left/right anchor keeps label box from crossing into the chart.
                if center_x >= overall_center_x:
                    box_x = max(center_x - 8, overall_center_x + overall_radius + 30)
                else:
                    box_x = min(center_x - box_w + 8, overall_center_x - overall_radius - box_w - 30)
                box_y = center_y - box_h // 2

                # Frame clamp for safe rendering on all angles.
                box_x = max(20, min(width - box_w - 20, box_x))
                box_y = max(280, min(height - box_h - 20, box_y))

                text_x = box_x + label_pad_x
                text_y = box_y + box_h // 2 + text_size[1] // 2 - 2

                if center_x >= overall_center_x:
                    connect_x = box_x
                else:
                    connect_x = box_x + box_w
                connect_y = box_y + box_h // 2

                cv2.line(frame, (anchor_x, anchor_y), (connect_x, connect_y), segment["color"], 2, line_type)
                cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), (28, 28, 28), -1)
                cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), segment["color"], 2)
                cv2.putText(frame, text, (text_x, text_y), font, label_scale, (245, 245, 245), label_thickness, line_type)

        # Overall progress indicator hand
        progress_angle = -90.0 + ((elapsed_seconds / total_seconds) * 360.0 if total_seconds > 0 else 0.0)
        rad = math.radians(progress_angle)
        hand_len = overall_radius + 20
        tip_x = int(overall_center_x + hand_len * math.cos(rad))
        tip_y = int(overall_center_y + hand_len * math.sin(rad))
        cv2.line(frame, (overall_center_x, overall_center_y), (tip_x, tip_y), (255, 255, 255), 4, line_type)
        cv2.circle(frame, (overall_center_x, overall_center_y), 10, (255, 255, 255), -1)

        # Overall digital timer inside the pie ring
        overall_time_scale = 7.5
        overall_time_thickness = 8
        overall_size = cv2.getTextSize(overall_time_str, font, overall_time_scale, overall_time_thickness)[0]
        overall_x = overall_center_x - overall_size[0] // 2
        overall_y = overall_center_y + overall_size[1] // 2
        cv2.putText(frame, overall_time_str, (overall_x, overall_y), font, overall_time_scale, (255, 255, 255), overall_time_thickness, line_type)
        elapsed_label = f"Elapsed: {overall_elapsed_str}"
        elapsed_scale = 1.0
        elapsed_thickness = 2
        elapsed_size = cv2.getTextSize(elapsed_label, font, elapsed_scale, elapsed_thickness)[0]
        cv2.putText(
            frame,
            elapsed_label,
            (overall_center_x - elapsed_size[0] // 2, overall_center_y + 175),
            font,
            elapsed_scale,
            (190, 190, 190),
            elapsed_thickness,
            line_type,
        )

        if is_time_up:
            time_up_text = "TIME'S UP"
            text_scale = 2.8
            text_thickness = 8
            text_size = cv2.getTextSize(time_up_text, font, text_scale, text_thickness)[0]
            box_margin_x = 50
            box_top = overall_center_y - 90
            box_bottom = overall_center_y + 90
            box_left = overall_center_x - (text_size[0] // 2) - box_margin_x
            box_right = overall_center_x + (text_size[0] // 2) + box_margin_x
            cv2.rectangle(frame, (box_left, box_top), (box_right, box_bottom), (0, 0, 0), -1)
            cv2.rectangle(frame, (box_left, box_top), (box_right, box_bottom), (255, 255, 255), 3)
            cv2.putText(
                frame,
                time_up_text,
                (overall_center_x - text_size[0] // 2, overall_center_y + text_size[1] // 2),
                font,
                text_scale,
                (255, 255, 255),
                text_thickness,
                line_type,
            )

        # Save frame sequence to stream
        if output_width != width or output_height != height:
            frame_out = cv2.resize(frame, (output_width, output_height), interpolation=cv2.INTER_AREA)
        else:
            frame_out = frame
        out.write(frame_out)
        
        # Simple rendering log interface
        log_every = max(1, writer_fps * 30)
        if frame_idx % log_every == 0:
            print(f"Rendering section [{current_sec['name']}] | section {section_time_str} | overall {overall_time_str}")
            
    out.release()
    print(f"Success! Video configuration written to '{output_filename}'")

if __name__ == "__main__":
    # Define your distinct timeline blocks here using duration_minutes.
    # Note: OpenCV utilizes BGR color formatting instead of standard RGB.
    
    presentation_flow = [
        {"name": "1. Presenter", "duration_minutes": 25, "color": (255, 100, 100)},
        {"name": "2. Discussant", "duration_minutes": 10, "color": (100, 255, 100)},
        {"name": "3. Q & A", "duration_minutes": 10, "color": (100, 100, 255)},        
    ]
    
    create_section_timer(
        presentation_flow,
        output_filename="timer_present_45mins.mp4",
        render_mode="ultra_fast",
    )
    
    
    presentation_flow = [
        {"name": "Opening Remarks", "duration_minutes": 15, "color": (255, 100, 100)},        
    ]
    
    create_section_timer(
        presentation_flow,
        output_filename="timer_opening_15mins.mp4",
        render_mode="ultra_fast",
    )
    
    
    presentation_flow = [
        {"name": "Keynote", "duration_minutes": 60, "color": (255, 100, 100)},        
    ]
    
    create_section_timer(
        presentation_flow,
        output_filename="timer_keynote_60mins.mp4",
        render_mode="ultra_fast",
    )
    
    presentation_flow = [
        {"name": "Policy Panel", "duration_minutes": 75, "color": (255, 100, 100)},        
    ]
    
    create_section_timer(
        presentation_flow,
        output_filename="timer_policy_panel_75mins.mp4",
        render_mode="ultra_fast",
    )
    