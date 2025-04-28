import json
import os
import shutil
import tempfile
import typing
import io
from pathlib import Path
import datetime

import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import birdnet_analyzer.gui.localization as loc
import birdnet_analyzer.gui.utils as gu
from birdnet_analyzer.visualization.data_processor import DataProcessor
from birdnet_analyzer.visualization.plotting.confidences import ConfidencePlotter
from birdnet_analyzer.visualization.plotting.time_distributions import TimeDistributionPlotter


class ProcessorState(typing.NamedTuple):
    """State of the DataProcessor."""
    processor: DataProcessor
    prediction_dir: str
    metadata_dir: str
    color_map: typing.Optional[typing.Dict[str, str]] = None
    class_thresholds: typing.Optional[pd.DataFrame] = None


def get_date_range(df: pd.DataFrame) -> tuple:
    """Get the earliest and latest dates from predictions."""
    try:
        if 'prediction_time' not in df.columns or df.empty:
            return None, None
        
        min_date = df['prediction_time'].min()
        max_date = df['prediction_time'].max()
        
        if pd.isna(min_date) or pd.isna(max_date):
            return None, None
            
        # Set time to start and end of day
        start_date = min_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = max_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date
    except Exception:
        return None, None


def convert_timestamp_to_datetime(timestamp):
    """Convert Gradio DateTime timestamp to pandas datetime."""
    if timestamp is None:
        return None
    try:
        # Convert timestamp to pandas datetime
        return pd.to_datetime(timestamp, unit='s')
    except:
        return None


def apply_datetime_filters(df, date_range_start, date_range_end, 
                         time_start_hour, time_start_minute, 
                         time_end_hour, time_end_minute):
    """Apply date and time filters to DataFrame."""
    if df.empty or 'prediction_time' not in df.columns:
        return df

    # Create a copy to avoid modifying original
    filtered_df = df.copy()
    
    # Apply date range filter if dates are provided
    if date_range_start is not None and date_range_end is not None:
        try:
            filtered_df = filtered_df[filtered_df['prediction_time'].notna()]
            start_date = convert_timestamp_to_datetime(date_range_start)
            end_date = convert_timestamp_to_datetime(date_range_end)
            
            if start_date and end_date:
                # Convert to pandas datetime if needed
                if not pd.api.types.is_datetime64_any_dtype(filtered_df['prediction_time']):
                    filtered_df['prediction_time'] = pd.to_datetime(filtered_df['prediction_time'])
                
                # Fix timezone issues by using normalized dates
                start_date = pd.Timestamp(start_date.date()) 
                end_date = pd.Timestamp(end_date.date()) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                
                # Filter by date range
                filtered_df = filtered_df[filtered_df['prediction_time'].dt.normalize().between(start_date, end_date)]
        
        except Exception as e:
            print(f"Date filtering error: {e}")
            return filtered_df

    # Apply time range filter if all time components are provided
    if all(x is not None for x in [time_start_hour, time_start_minute, time_end_hour, time_end_minute]):
        try:
            # Convert times to datetime.time objects
            start_time = datetime.time(int(time_start_hour), int(time_start_minute), 0, 0)
            end_time = datetime.time(int(time_end_hour), int(time_end_minute), 59, 999999)
            
            # Filter by time of day if prediction_time is datetime
            if pd.api.types.is_datetime64_any_dtype(filtered_df['prediction_time']):
                filtered_df = filtered_df[filtered_df['prediction_time'].dt.time.between(start_time, end_time)]
                
        except Exception as e:
            print(f"Time filtering error: {e}")
            return filtered_df

    return filtered_df


def apply_class_thresholds(df: pd.DataFrame, thresholds_df: pd.DataFrame, class_col: str, conf_col: str) -> pd.DataFrame:
    """Apply class-specific confidence thresholds."""
    if df.empty:
        return df
    if thresholds_df is None or thresholds_df.empty:
        return df

    try:
        # Ensure threshold column is numeric and clip values
        thresholds_df = thresholds_df.copy()
        thresholds_df['Threshold'] = pd.to_numeric(thresholds_df['Threshold'], errors='coerce')
        thresholds_df['Threshold'] = thresholds_df['Threshold'].fillna(0.10).clip(0.01, 0.99) # Default 0.10 if invalid

        # Prepare for merge
        threshold_map = thresholds_df.set_index('Class')['Threshold']
        
        # Map thresholds to the main dataframe
        df['class_threshold'] = df[class_col].map(threshold_map)
        
        # Apply default threshold if class not in map (shouldn't happen with proper init)
        df['class_threshold'] = df['class_threshold'].fillna(0.10) 

        # Filter based on class-specific threshold
        filtered_df = df[df[conf_col] >= df['class_threshold']].copy()
        
        # Drop the temporary threshold column
        filtered_df.drop(columns=['class_threshold'], inplace=True)
        
        return filtered_df

    except Exception as e:
        print(f"Error applying class thresholds: {e}")
        # Return original df if error occurs
        return df


def build_visualization_tab():
    """
    Builds a Gradio tab for loading and plotting prediction data only,
    using ConfidencePlotter. Annotation logic and metric calculations
    have been removed.
    """

    # Default columns for predictions (kept for user convenience)
    prediction_default_columns = {
        "Start Time": "Begin Time (s)",
        "End Time": "End Time (s)",
        "Class": "Common Name",
        "Recording": "Begin Path",
        "Confidence": "Confidence",
        "Correctness": "correctness",
    }

    # Default columns for metadata
    metadata_default_columns = {
        "Site": "Site",
        "X": "lat",
        "Y": "lon",
    }

    localized_column_labels = {
        "Start Time": loc.localize("eval-tab-column-start-time-label"),
        "End Time": loc.localize("eval-tab-column-end-time-label"),
        "Class": loc.localize("eval-tab-column-class-label"),
        "Recording": loc.localize("eval-tab-column-recording-label"),
        "Confidence": loc.localize("eval-tab-column-confidence-label"),
        "Correctness": loc.localize("viz-tab-column-correctness-label"),
        "Site": loc.localize("viz-tab-column-site-label"),
        "X": loc.localize("viz-tab-column-latitude-label"),
        "Y": loc.localize("viz-tab-column-longitude-label"),
    }

    def get_columns_from_uploaded_files(files):
        """
        Reads the header row of each file to discover available columns.
        """
        columns = set()
        if files:
            for file_obj in files:
                try:
                    df = pd.read_csv(file_obj, sep=None, engine="python", nrows=0)
                    columns.update(df.columns)
                except Exception as e:
                    print(f"Error reading file {file_obj}: {e}")
                    gr.Warning(f"{loc.localize('eval-tab-warning-error-reading-file')} {file_obj}")
        return sorted(list(columns))

    def save_uploaded_files(files):
        """
        Saves uploaded files into a temporary directory and returns its path.
        """
        if not files:
            return None
        temp_dir = tempfile.mkdtemp()
        for file_obj in files:
            dest_path = os.path.join(temp_dir, os.path.basename(file_obj))
            shutil.copy(file_obj, dest_path)
        return temp_dir

    def initialize_processor(
        prediction_files,
        pred_start_time,
        pred_end_time,
        pred_class,
        pred_confidence,
        pred_recording,
        pred_correctness=None,  # Add correctness parameter with default
        prediction_dir=None,
    ):
        """Creates a simplified DataProcessor for predictions only."""
        if not prediction_files:
            return [], [], None, None

        try:
            # Initialize processor
            if prediction_dir is None:
                prediction_dir = save_uploaded_files(prediction_files)

            # Debug just number of files
            print(f"\nProcessing {len(prediction_files)} prediction files")
            print(f"Using prediction directory: {prediction_dir}")

            # Set up column mappings with proper fallbacks
            cols_pred = {}
            for key, default in prediction_default_columns.items():
                if key == "Start Time":
                    cols_pred[key] = pred_start_time or default
                elif key == "End Time":
                    cols_pred[key] = pred_end_time or default
                elif key == "Class":
                    cols_pred[key] = pred_class or default
                elif key == "Confidence":
                    cols_pred[key] = pred_confidence or default
                elif key == "Recording":
                    cols_pred[key] = pred_recording or default
                elif key == "Correctness":
                    cols_pred[key] = pred_correctness or default

            print("Using column mappings:", cols_pred)

            proc = DataProcessor(
                prediction_directory_path=prediction_dir,
                prediction_file_name=None,
                columns_predictions=cols_pred,
            )
            
            # Get data and extract unique values
            df = proc.get_data()
            
            # Debug dataframe shape and columns
            print(f"\nLoaded DataFrame shape: {df.shape}")
            print(f"DataFrame columns: {df.columns}")
            
            avail_classes = list(proc.classes) 
            print(f"\nFound {len(avail_classes)} unique classes")
            
            # Get and clean up recording names consistently (strip and lowercase)
            recordings = df["recording_filename"].dropna().unique()
            avail_recordings = []
            for rec in recordings:
                if isinstance(rec, str):
                    clean_name = os.path.splitext(os.path.basename(rec.strip()))[0].lower()
                    if clean_name and clean_name not in avail_recordings:
                        avail_recordings.append(clean_name)
            avail_recordings.sort()
            print(f"Found {len(avail_recordings)} unique recordings")

            return avail_classes, avail_recordings, proc, prediction_dir

        except Exception as e:
            print(f"Error in initialize_processor: {e}")
            raise gr.Error(f"Error initializing processor: {str(e)}")

    def update_prediction_columns(uploaded_files):
        """
        Called when user selects prediction files. Reads headers and updates dropdowns.
        """
        cols = get_columns_from_uploaded_files(uploaded_files)
        cols = [""] + cols
        updates = []
        for label in ["Start Time", "End Time", "Class", "Confidence", "Recording", "Correctness"]:
            default_val = prediction_default_columns.get(label)
            val = default_val if default_val in cols else None
            updates.append(gr.update(choices=cols, value=val))
        return updates

    def update_metadata_columns(uploaded_files):
        """
        Called when user selects metadata files. Reads headers and updates dropdowns.
        """
        cols = set()
        if uploaded_files:
            for file_obj in uploaded_files:
                try:
                    # Try reading with CSV engine first
                    df = pd.read_csv(file_obj, nrows=0)
                    cols.update(df.columns)
                except Exception:
                    try:
                        # Fallback to python engine with automatic delimiter detection
                        df = pd.read_csv(file_obj, sep=None, engine="python", nrows=0)
                        cols.update(df.columns)
                    except Exception as e:
                        print(f"Error reading file {file_obj}: {e}")
                        gr.Warning(f"{loc.localize('eval-tab-warning-error-reading-file')} {file_obj}")
        
        cols = [""] + sorted(list(cols))
        updates = []
        for label in ["Site", "X", "Y"]:
            default_val = metadata_default_columns.get(label)
            val = default_val if default_val in cols else None
            updates.append(gr.update(choices=cols, value=val))
        return updates

    def update_selections(
        prediction_files,
        metadata_files,
        pred_start_time,
        pred_end_time,
        pred_class,
        pred_confidence,
        pred_recording,
        pred_correctness,
        meta_site,
        meta_x,
        meta_y,
        current_classes,
        current_recordings,
    ):
        """
        Called to create or update the processor based on current file uploads and column selections.
        Preserves any selected classes/recordings that remain valid.
        Initializes the class threshold DataFrame and makes the update button visible.
        """
        prediction_dir = save_uploaded_files(prediction_files)
        metadata_dir = save_uploaded_files(metadata_files)
        
        avail_classes, avail_recordings, proc, prediction_dir = initialize_processor(
            prediction_files,
            pred_start_time,
            pred_end_time,
            pred_class,
            pred_confidence,
            pred_recording,
            pred_correctness,
            prediction_dir,
        )
        
        # Initialize class thresholds DataFrame
        class_thresholds_init_df = None
        threshold_df_update = gr.update(visible=False, value=None) # Default to hidden
        threshold_json_btn_update = gr.update(visible=False) # Update for JSON select button
        threshold_download_btn_update = gr.update(visible=False) # Update for download button
        
        if proc:
            # Create DataFrame for thresholds
            class_thresholds_init_df = pd.DataFrame({
                'Class': sorted(avail_classes),
                'Threshold': [0.10] * len(avail_classes) # Default threshold
            })
            threshold_df_update = gr.update(visible=True, value=class_thresholds_init_df)
            threshold_json_btn_update = gr.update(visible=True) # Make JSON select button visible
            threshold_download_btn_update = gr.update(visible=True) # Make download button visible

            state = ProcessorState(
                processor=proc, 
                prediction_dir=prediction_dir, 
                metadata_dir=metadata_dir,
                class_thresholds=class_thresholds_init_df # Store initial thresholds in state
            )
        else:
            state = None # No processor created

        # Keep current selections if they exist in available options
        new_classes = []
        new_recordings = []

        if current_classes:
            new_classes = [c for c in current_classes if c in avail_classes]
        if current_recordings:
            normalized_current = [os.path.splitext(os.path.basename(r.strip()))[0].lower() 
                               for r in current_recordings if isinstance(r, str)]
            new_recordings = [r for r in normalized_current if r in avail_recordings]

        # Default to all available if no valid selections remain
        if not new_classes:
            new_classes = avail_classes
        if not new_recordings:
            new_recordings = avail_recordings

        return (
            gr.update(choices=avail_classes, value=new_classes),
            gr.update(choices=avail_recordings, value=new_recordings),
            state,
            threshold_df_update, # Return update for the DataFrame UI
            threshold_json_btn_update, # Return update for JSON select button
            threshold_download_btn_update # Return update for download button
        )

    def update_datetime_defaults(processor_state):
        """Update the default date range based on available predictions."""
        if not processor_state or not processor_state.processor:
            return [gr.update()] * 6  # Updated for 6 outputs (2 dates + 4 time dropdowns)
        
        df = processor_state.processor.get_data()
        start_date, end_date = get_date_range(df)
        
        return [
            gr.update(value=start_date),
            gr.update(value=end_date),
            gr.update(value="00"),  # Start hour
            gr.update(value="00"),  # Start minute
            gr.update(value="23"),  # End hour
            gr.update(value="59"),  # End minute
        ]

    def combine_time_components(hour, minute):
        """Combine hour and minute components into a time string."""
        return f"{hour}:{minute}"

    def plot_predictions_action(
        proc_state: ProcessorState,
        selected_classes_list,
        selected_recordings_list,
        date_range_start,
        date_range_end,
        time_start_hour,
        time_start_minute,
        time_end_hour,
        time_end_minute,
    ):
        """Uses ConfidencePlotter to plot confidence distributions for the selected classes."""
        if not proc_state or not proc_state.processor:
            raise gr.Error(loc.localize("eval-tab-error-calc-metrics-first"))

        df = proc_state.processor.get_data()
        if df.empty:
            raise gr.Error("No predictions to show.")

        # Apply class and recording filters first
        col_class = proc_state.processor.get_column_name("Class")
        conf_col = proc_state.processor.get_column_name("Confidence")
        
        if selected_classes_list:
            df = df[df[col_class].isin(selected_classes_list)]
        if selected_recordings_list:
            selected_recordings_list = [rec.lower() for rec in selected_recordings_list]
            df["recording_filename"] = df["recording_filename"].apply(lambda x: os.path.splitext(os.path.basename(x.strip()))[0].lower() if isinstance(x, str) else x)
            df = df[df["recording_filename"].isin(selected_recordings_list)]

        # Apply date and time filters
        df = apply_datetime_filters(
            df, 
            date_range_start, 
            date_range_end, 
            time_start_hour, 
            time_start_minute, 
            time_end_hour, 
            time_end_minute
        )
        
        if df.empty:
            raise gr.Error("No predictions match the selected date/time filters.")

        # Create histogram plot (using Plotly) with fixed 10 bins (handled in the method)
        plotter = ConfidencePlotter(
            data=df,
            class_col=col_class,
            conf_col=conf_col
        )

        try:
            fig_hist = plotter.plot_histogram_plotly(title="Histogram of Confidence Scores by Class")
            new_state = ProcessorState(
                processor=proc_state.processor,
                prediction_dir=proc_state.prediction_dir,
                metadata_dir=proc_state.metadata_dir,
                color_map=proc_state.color_map,
                class_thresholds=proc_state.class_thresholds
            )
            return [new_state, gr.update(visible=True, value=fig_hist)]
        except Exception as e:
            raise gr.Error(f"Error creating plots: {str(e)}")

    def plot_temporal_scatter(
        proc_state: ProcessorState,
        selected_classes_list,
        selected_recordings_list,
        date_range_start,
        date_range_end,
        time_start_hour,
        time_start_minute,
        time_end_hour,
        time_end_minute,
        meta_x=None,
        meta_y=None,
        correctness_mode="Ignore correctness flags"  # Add correctness_mode parameter with default
    ):
        """Creates a temporal scatter plot showing detections by date and time of day."""
        if not proc_state or not proc_state.processor:
            raise gr.Error("Please load predictions first")
            
        if proc_state.class_thresholds is None:
            raise gr.Error("Class thresholds not initialized. Load data first.")
            
        # Validate thresholds from state
        validated_thresholds_df = proc_state.class_thresholds
            
        # Get data and apply all filters
        df = proc_state.processor.get_data()
        
        # Apply class and recording filters
        col_class = proc_state.processor.get_column_name("Class")
        conf_col = proc_state.processor.get_column_name("Confidence")
        corr_col = proc_state.processor.get_column_name("Correctness")
        
        # Check if correctness column exists; if not, try both capitalization forms
        if corr_col not in df.columns:
            # Try both 'correctness' and 'Correctness'
            alt_corr_col = 'correctness' if corr_col == 'Correctness' else 'Correctness'
            if alt_corr_col in df.columns:
                print(f"Switching to alternative correctness column: '{alt_corr_col}'")
                corr_col = alt_corr_col
            else:
                # Create an empty correctness column if none exists
                print(f"No correctness column found, creating a placeholder")
                df[corr_col] = None
        
        if selected_classes_list:
            df = df[df[col_class].isin(selected_classes_list)]
        if selected_recordings_list:
            selected_recordings_list = [rec.lower() for rec in selected_recordings_list]
            df["recording_filename"] = df["recording_filename"].apply(
                lambda x: os.path.splitext(os.path.basename(x.strip()))[0].lower() 
                if isinstance(x, str) else x
            )
            df = df[df["recording_filename"].isin(selected_recordings_list)]
            
        # Apply class-specific confidence thresholds
        df = apply_class_thresholds(df, validated_thresholds_df, col_class, conf_col)
        
        # Apply date and time filters
        df = apply_datetime_filters(
            df, 
            date_range_start, 
            date_range_end,
            time_start_hour,
            time_start_minute,
            time_end_hour,
            time_end_minute
        )
        
        # Normalize correctness values
        df[corr_col] = df[corr_col].map({
            'true': True, 'True': True, True: True, 1: True,
            'false': False, 'False': False, False: False, 0: False,
            'nan': None, 'none': None, '': None, 'null': None, 'NA': None
        }, na_action='ignore')
        
        # Create a human-readable correctness column for display
        df['correctness_display'] = df[corr_col].apply(
            lambda x: "Correct" if x == True else "Incorrect" if x == False else "Unspecified"
        )
        
        # Apply correctness filter based on selected mode
        if correctness_mode == "Show only correct":
            df = df[df[corr_col] == True]
        elif correctness_mode == "Show only incorrect":
            df = df[df[corr_col] == False]
        elif correctness_mode == "Show only unspecified":
            df = df[df[corr_col].isna()]
        
        if df.empty:
            raise gr.Error("No data matches the selected filters")
        
        # Ensure we have datetime data for plotting
        if 'prediction_time' not in df.columns or df['prediction_time'].isnull().all():
            raise gr.Error("Prediction time data is not available")
        
        # Extract date and time components for plotting
        df['date'] = df['prediction_time'].dt.date
        
        # Convert time to decimal hours for plotting (e.g. 14:30 = 14.5)
        df['decimal_time'] = df['prediction_time'].dt.hour + df['prediction_time'].dt.minute/60 + df['prediction_time'].dt.second/3600
        
        # Get or create color map for consistency with other plots
        all_classes = sorted(df[col_class].unique())
        color_map = proc_state.color_map or {}
        
        # If no color map exists or new classes found, create/update it
        if not color_map or not all(cls in color_map for cls in all_classes):
            base_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink']
            existing_classes = list(color_map.keys())
            new_classes = [cls for cls in all_classes if cls not in existing_classes]
            next_color_idx = len(existing_classes)
            
            for cls in new_classes:
                color_map[cls] = base_colors[next_color_idx % len(base_colors)]
                next_color_idx += 1
        
        # Define marker symbols for each correctness state - moved outside the if block so it's available to all modes
        correctness_symbols = {
            "Correct": "circle",
            "Incorrect": "x", 
            "Unspecified": "diamond"
        }
        
        # Create the plot - different approach based on correctness mode
        fig = go.Figure()
        
        if correctness_mode == "Distinguish all":
            # For each class, create separate traces for each correctness state
            for cls in all_classes:
                cls_color = color_map.get(cls)
                cls_data = df[df[col_class] == cls]
                
                # For each correctness state, create a separate trace
                for corr_state, symbol in correctness_symbols.items():
                    state_data = cls_data[cls_data['correctness_display'] == corr_state]
                    if not state_data.empty:
                        fig.add_trace(go.Scatter(
                            x=state_data['date'],
                            y=state_data['decimal_time'],
                            mode='markers',
                            name=f"{cls} - {corr_state}",
                            marker=dict(
                                color=cls_color,
                                symbol=symbol,
                                size=8,
                                opacity=0.3,
                            ),
                            hovertemplate=(
                                "Date: %{x|%Y-%m-%d}<br>" +
                                "Time: %{y:.2f} hrs<br>" +
                                "Species: " + cls + "<br>" +
                                "Status: " + corr_state + "<br>" +
                                "Confidence: " + state_data[conf_col].astype(str) + "<br>" +
                                "<extra></extra>"
                            )
                        ))
        elif correctness_mode == "Show only correct":
            # Use the same marker as "Correct" in distinguish mode (circle)
            for cls in all_classes:
                cls_color = color_map.get(cls)
                cls_data = df[df[col_class] == cls]
                
                if not cls_data.empty:
                    fig.add_trace(go.Scatter(
                        x=cls_data['date'],
                        y=cls_data['decimal_time'],
                        mode='markers',
                        name=cls,
                        marker=dict(
                            color=cls_color,
                            symbol=correctness_symbols["Correct"],  # Use circle symbol
                            size=8,
                            opacity=0.3,
                        ),
                        hovertemplate=(
                            "Date: %{x|%Y-%m-%d}<br>" +
                            "Time: %{y:.2f} hrs<br>" +
                            "Species: " + cls + "<br>" +
                            "Status: Correct<br>" +
                            "Confidence: " + cls_data[conf_col].astype(str) + "<br>" +
                            "<extra></extra>"
                        )
                    ))
        elif correctness_mode == "Show only incorrect":
            # Use the same marker as "Incorrect" in distinguish mode (x)
            for cls in all_classes:
                cls_color = color_map.get(cls)
                cls_data = df[df[col_class] == cls]
                
                if not cls_data.empty:
                    fig.add_trace(go.Scatter(
                        x=cls_data['date'],
                        y=cls_data['decimal_time'],
                        mode='markers',
                        name=cls,
                        marker=dict(
                            color=cls_color,
                            symbol=correctness_symbols["Incorrect"],  # Use x symbol
                            size=8,
                            opacity=0.3,
                        ),
                        hovertemplate=(
                            "Date: %{x|%Y-%m-%d}<br>" +
                            "Time: %{y:.2f} hrs<br>" +
                            "Species: " + cls + "<br>" +
                            "Status: Incorrect<br>" +
                            "Confidence: " + cls_data[conf_col].astype(str) + "<br>" +
                            "<extra></extra>"
                        )
                    ))
        elif correctness_mode == "Show only unspecified":
            # Use the same marker as "Unspecified" in distinguish mode (diamond)
            for cls in all_classes:
                cls_color = color_map.get(cls)
                cls_data = df[df[col_class] == cls]
                
                if not cls_data.empty:
                    fig.add_trace(go.Scatter(
                        x=cls_data['date'],
                        y=cls_data['decimal_time'],
                        mode='markers',
                        name=cls,
                        marker=dict(
                            color=cls_color,
                            symbol=correctness_symbols["Unspecified"],  # Use diamond symbol
                            size=8,
                            opacity=0.3,
                        ),
                        hovertemplate=(
                            "Date: %{x|%Y-%m-%d}<br>" +
                            "Time: %{y:.2f} hrs<br>" +
                            "Species: " + cls + "<br>" +
                            "Status: Unspecified<br>" +
                            "Confidence: " + cls_data[conf_col].astype(str) + "<br>" +
                            "<extra></extra>"
                        )
                    ))
        else:
            # Default mode - "Ignore correctness flags" - use standard plotly express scatter
            fig = px.scatter(
                df,
                x='date',
                y='decimal_time',
                color=col_class,
                color_discrete_map=color_map,
                hover_data=[col_class, conf_col],
                opacity=0.3,
                title="Temporal Distribution of Detections"
            )
            
            # Format hover template to show time in HH:MM format
            for trace in fig.data:
                trace.hovertemplate = (
                    "Date: %{x|%Y-%m-%d}<br>" +
                    "Time: %{customdata[1]:.2f} (%{y:.2f} hrs)<br>" +
                    "Species: %{customdata[0]}<br>" +
                    "Confidence: %{customdata[1]:.3f}<br>" +
                    "<extra></extra>"
                )
        
        # Calculate mean latitude and longitude for sunrise/sunset calculations
        # Try to get coordinates from the data or use a default
        try:
            # First check if we have latitude/longitude in the dataframe
            if 'latitude' in df.columns and 'longitude' in df.columns and not df['latitude'].isnull().all() and not df['longitude'].isnull().all():
                mean_lat = df['latitude'].mean()
                mean_lon = df['longitude'].mean()
                print(f"Using coordinates from data: {mean_lat}, {mean_lon}")
            # If not, see if we can get them from metadata using provided column names
            elif proc_state.metadata_dir:
                meta_files = list(Path(proc_state.metadata_dir).glob("*.csv"))
                if not meta_files:
                    raise ValueError("No metadata CSV files found in the metadata directory")
                    
                metadata_df = pd.read_csv(meta_files[0])
                print(f"Metadata columns available: {metadata_df.columns.tolist()}")
                    
                # First try using the explicitly provided meta_x and meta_y from UI
                lat_col = meta_x
                lon_col = meta_y
                    
                # If not provided, try common column names
                if not lat_col or not lon_col or lat_col not in metadata_df.columns or lon_col not in metadata_df.columns:
                    print("Metadata column names not provided or invalid, trying common column names...")
                    lat_cols = ['latitude', 'lat', 'y', 'Y', 'LAT', 'Latitude']
                    lon_cols = ['longitude', 'lon', 'long', 'x', 'X', 'LON', 'Longitude']
                        
                    lat_col = next((col for col in lat_cols if col in metadata_df.columns), None)
                    lon_col = next((col for col in lon_cols if col in metadata_df.columns), None)
                
                if lat_col is None or lon_col is None:
                    raise ValueError(f"Could not find latitude/longitude columns in metadata. Available columns: {', '.join(metadata_df.columns)}")
                        
                print(f"Using metadata columns: {lat_col} for latitude, {lon_col} for longitude")
                mean_lat = pd.to_numeric(metadata_df[lat_col], errors='coerce').mean()
                mean_lon = pd.to_numeric(metadata_df[lon_col], errors='coerce').mean()
            else:
                raise ValueError("No location data available. Please provide metadata with latitude and longitude.")
                        
            # Check that we have valid coordinates
            if pd.isna(mean_lat) or pd.isna(mean_lon):
                raise ValueError("Invalid coordinates (NaN values)")
                        
            print(f"Using average location: {mean_lat}, {mean_lon}")
                        
            # Try to import astral for sunrise/sunset calculations
            try:
                from astral import LocationInfo
                from astral.sun import sun
                from datetime import timedelta, date
                print("Using Astral for sunrise/sunset calculations")
                
                # Get unique dates in the data
                unique_dates = sorted(df['date'].unique())
                if not unique_dates:
                    raise ValueError("No valid dates found in the data")
                    
                # Create location info for the site's average location
                site = LocationInfo("RecordingSite", "Region", "UTC", mean_lat, mean_lon)
                
                # Define color for sunrise/sunset lines - use purple (solid lines)
                sun_line_color = "purple"
                
                # Calculate sunrise/sunset only every 10 days, starting from the first date
                first_date = min(unique_dates)
                last_date = max(unique_dates)
                
                # Function to convert a date to days since first date
                def days_since_first(d):
                    if isinstance(d, pd.Timestamp):
                        d = d.date()
                    return (d - first_date).days
                    
                # Find dates to calculate (every 10 days)
                calculation_dates = []
                current_date = first_date
                while current_date <= last_date:
                    calculation_dates.append(current_date)
                    current_date += timedelta(days=10)
                
                # Include last date if it's not already included
                if calculation_dates[-1] != last_date:
                    calculation_dates.append(last_date)
                    
                print(f"Calculating sunrise/sunset for {len(calculation_dates)} dates " 
                      f"(every 10 days from {first_date} to {last_date})")
                    
                # Calculate sunrise/sunset for the selected dates
                sunrise_data = {}  # {date: decimal_time}
                sunset_data = {}   # {date: decimal_time}
                
                for calc_date in calculation_dates:
                    try:
                        sun_info = sun(site.observer, date=calc_date)
                        
                        # Extract sunrise and sunset times
                        sunrise_time = sun_info['sunrise']
                        sunset_time = sun_info['sunset']
                        
                        # Remove timezone info if present
                        if sunrise_time.tzinfo is not None:
                            sunrise_time = sunrise_time.replace(tzinfo=None)
                        if sunset_time.tzinfo is not None:
                            sunset_time = sunset_time.replace(tzinfo=None)
                        
                        # Convert to decimal hours for plotting
                        sunrise_decimal = sunrise_time.hour + sunrise_time.minute/60 + sunrise_time.second/3600
                        sunset_decimal = sunset_time.hour + sunset_time.minute/60 + sunset_time.second/3600
                        
                        # Store calculations
                        sunrise_data[calc_date] = sunrise_decimal
                        sunset_data[calc_date] = sunset_decimal
                        
                        print(f"Date {calc_date}: Sunrise at {sunrise_decimal:.2f}h, Sunset at {sunset_decimal:.2f}h")
                        
                    except Exception as e:
                        print(f"Error calculating sunrise/sunset for {calc_date}: {str(e)}")
                
                # Create continuous sunrise and sunset lines
                # First prepare x and y values for each line
                sunrise_x = []
                sunrise_y = []
                sunset_x = []
                sunset_y = []
                
                # Convert calculated points to lists for plotting
                for date_val in sorted(sunrise_data.keys()):
                    sunrise_x.append(date_val)
                    sunrise_y.append(sunrise_data[date_val])
                    
                    sunset_x.append(date_val)
                    sunset_y.append(sunset_data[date_val])
                
                # Add sunrise line as a continuous line
                fig.add_trace(
                    go.Scatter(
                        x=sunrise_x,
                        y=sunrise_y,
                        mode='lines',
                        line=dict(color=sun_line_color, width=2),
                        name='Sunrise',
                        showlegend=True
                    )
                )
                
                # Add sunset line as a continuous line
                fig.add_trace(
                    go.Scatter(
                        x=sunset_x,
                        y=sunset_y,
                        mode='lines',
                        line=dict(color=sun_line_color, width=2),
                        name='Sunset',
                        showlegend=True
                    )
                )
                    
            except ImportError:
                print("Astral is not installed. Install with: pip install astral")
                gr.Warning("For sunrise/sunset lines, install Astral: pip install astral")
                    
        except Exception as e:
            print(f"Error adding sunrise/sunset lines: {str(e)}")
            import traceback
            traceback.print_exc()  # Print the full traceback for debugging
            gr.Warning(f"Could not add sunrise/sunset lines: {str(e)[:100]}...")
        
        # Customize layout
        fig.update_layout(
            title="Temporal Distribution of Detections",
            xaxis_title="Date",
            yaxis_title="Time of Day (hours)",
            yaxis=dict(
                tickmode='array',
                tickvals=[0, 3, 6, 9, 12, 15, 18, 21, 24],
                ticktext=['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00', '24:00']
            ),
            legend_title="Species",
            legend=dict(
                x=1.02, 
                y=1,
                itemsizing='constant'  # Makes legend symbols the same size
            ),
            margin=dict(r=150),  # Add right margin for legend
        )
        
        # Update state with new color map for consistency
        new_state = ProcessorState(
            processor=proc_state.processor,
            prediction_dir=proc_state.prediction_dir,
            metadata_dir=proc_state.metadata_dir,
            color_map=color_map,
            class_thresholds=validated_thresholds_df
        )
        
        return [new_state, gr.update(value=fig, visible=True)]

    def plot_spatial_distribution(
        proc_state: ProcessorState,
        meta_x,
        meta_y,
        meta_site,
        date_range_start,
        date_range_end,
        time_start_hour,
        time_start_minute,
        time_end_hour,
        time_end_minute,
    ):
        """Plot spatial distribution of predictions by class."""
        if not proc_state or not proc_state.processor:
            raise gr.Error("Please load predictions first")
            
        if proc_state.class_thresholds is None:
            raise gr.Error("Class thresholds not initialized. Load data first.") 
            
        try:
            # Validate thresholds from state
            validated_thresholds_df = proc_state.class_thresholds

            # Read metadata file from the provided directory
            meta_files = list(Path(proc_state.metadata_dir).glob("*.csv"))
            if not meta_files:
                raise gr.Error("No metadata files found")
            metadata_df = pd.read_csv(meta_files[0])
            
            # Ensure expected source columns exist
            if meta_x not in metadata_df.columns or meta_y not in metadata_df.columns:
                raise gr.Error("Metadata file missing expected coordinate columns.")
            # Convert columns and create standardized 'latitude' and 'longitude'
            metadata_df = metadata_df.copy()
            metadata_df['latitude'] = pd.to_numeric(metadata_df[meta_x], errors='coerce')
            metadata_df['longitude'] = pd.to_numeric(metadata_df[meta_y], errors='coerce')
            
            # Store all unique locations from metadata before filtering
            all_locations_df = metadata_df.copy()
            all_locations_df = all_locations_df.rename(columns={meta_site: 'site_name'})
            all_locations_df = all_locations_df[['site_name', 'latitude', 'longitude']].drop_duplicates()
            
            # Set metadata into processor
            proc_state.processor.set_metadata(metadata_df, site_col=meta_site, lat_col='latitude', lon_col='longitude')
            
            # Get prediction data and apply filters
            df = proc_state.processor.get_data()
            
            # Apply class-specific confidence threshold filter using validated thresholds
            conf_col = proc_state.processor.get_column_name("Confidence")
            class_col = proc_state.processor.get_column_name("Class")
            df = apply_class_thresholds(df, validated_thresholds_df, class_col, conf_col)
            
            # Apply date and time filters
            df = apply_datetime_filters(
                df, 
                date_range_start, 
                date_range_end, 
                time_start_hour, 
                time_start_minute, 
                time_end_hour, 
                time_end_minute
            )
            
            class_col = proc_state.processor.get_column_name("Class")
            # Ensure that latitude and longitude exist in the data after merge
            for col in ['latitude', 'longitude']:
                if col not in df.columns:
                    raise gr.Error(f"Column '{col}' is missing after merging metadata.")
            
            # Create aggregated dataframe with counts by location and class
            agg_df = df.groupby(['site_name', 'latitude', 'longitude', class_col]).size().reset_index(name='count')
            
            # Create or retrieve color map for consistency with other plots
            all_classes = sorted(df[class_col].unique())
            color_map = {}
            
            # Use existing color map from state if available
            if proc_state.color_map:
                color_map = proc_state.color_map.copy()
                # Add any new classes that aren't in the existing map
                base_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink']
                next_color_idx = len(color_map)
                for cls in all_classes:
                    if cls not in color_map:
                        color_map[cls] = base_colors[next_color_idx % len(base_colors)]
                        next_color_idx += 1
            else:
                # Create new color map using same method as ConfidencePlotter
                base_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink']
                colors = base_colors * (1 + len(all_classes) // len(base_colors))
                color_map = {cls: colors[i] for i, cls in enumerate(all_classes)}
                
            # Special case for empty results
            if agg_df.empty:
                # If no detections match filters, still show the locations
                agg_df = all_locations_df.copy()
                agg_df[class_col] = "No Detections"
                agg_df['count'] = 0
            else:
                # Find locations with no detections in the filtered dataset
                active_locations = set(agg_df[['site_name', 'latitude', 'longitude']].itertuples(index=False, name=None))
                all_locations = set(all_locations_df.itertuples(index=False, name=None))
                missing_locations = all_locations - active_locations
                
                # Create DataFrame for locations with no detections
                if missing_locations:
                    missing_df = pd.DataFrame(list(missing_locations), columns=['site_name', 'latitude', 'longitude'])
                    missing_df[class_col] = "No Detections"
                    missing_df['count'] = 0
                    
                    # Combine with aggregated data
                    agg_df = pd.concat([agg_df, missing_df], ignore_index=True)
            
            # Always add "No Detections" to the color map
            color_map["No Detections"] = 'black'
            
            # Update the processor state with the color map for future consistency
            new_state = ProcessorState(
                processor=proc_state.processor,
                prediction_dir=proc_state.prediction_dir,
                metadata_dir=proc_state.metadata_dir,
                color_map=color_map,
                class_thresholds=validated_thresholds_df
            )
            
            # Get sorted classes for category order, with "No Detections" first
            sorted_classes = sorted(agg_df[class_col].unique())
            if "No Detections" in sorted_classes:
                sorted_classes.remove("No Detections")
                sorted_classes = ["No Detections"] + sorted_classes
            
            # Create the scatter mapbox plot
            fig = px.scatter_mapbox(
                agg_df,
                lat='latitude',
                lon='longitude',
                size='count',
                color=class_col,
                category_orders={class_col: sorted_classes},
                color_discrete_map=color_map,
                hover_data=['site_name', 'count'],
                size_max=50,
                zoom=10,
                height=600,
                title="Spatial Distribution of Predictions by Class"
            )
            
            # Adjust marker sizes - special case for "No Detections"
            for i, trace in enumerate(fig.data):
                if trace.name == "No Detections":
                    # Set fixed small size for "No Detections" markers
                    fig.data[i].marker.size = 8
                    fig.data[i].marker.sizemode = "diameter"
                    fig.data[i].marker.sizeref = 1
                    fig.data[i].marker.sizemin = 8
                else:
                    # Scale other markers by detection count
                    max_count = max(agg_df['count']) if len(agg_df[agg_df['count'] > 0]) > 0 else 1
                    size_scale = 50
                    sizeref = 2.0 * max_count / (size_scale**2)
                    fig.data[i].marker.sizeref = sizeref
                    fig.data[i].marker.sizemin = 5
                    fig.data[i].marker.sizemode = 'area'
                
                # Set opacity for all markers
                fig.data[i].marker.opacity = 0.8
            
            fig.update_layout(
                mapbox_style='open-street-map',
                margin={"r":0,"t":30,"l":0,"b":0},
                legend_title="Class",
                showlegend=True,
                mapbox=dict(center=dict(lat=agg_df['latitude'].mean(), lon=agg_df['longitude'].mean()), zoom=10),
                modebar=dict(
                    orientation='h',  # Horizontal orientation
                    bgcolor='rgba(255, 255, 255, 0.8)',
                    color='#333333',
                    activecolor='#FF4B4B'
                ),
                modebar_add=[
                    'zoom', 'zoomIn', 'zoomOut', 'resetViews'
                ],
                margin_pad=10,  # Add some padding
                margin_t=50     # Add top margin for modebar
            )
            
            # Update hover template based on whether it's a "No Detections" point
            for i, trace in enumerate(fig.data):
                if trace.name == "No Detections":
                    fig.data[i].hovertemplate = (
                        "Site: %{customdata[0]}<br>"
                        "Status: No Detections<br>"
                        "Latitude: %{lat:.2f}<br>"
                        "Longitude: %{lon:.2f}<br>"
                        "<extra></extra>"
                    )
                else:
                    fig.data[i].hovertemplate = (
                        "Site: %{customdata[0]}<br>"
                        "Count: %{customdata[1]}<br>"
                        "Latitude: %{lat:.2f}<br>"
                        "Longitude: %{lon:.2f}<br>"
                        "<extra></extra>"
                    )
            
            return [new_state, gr.update(value=fig, visible=True)]
        except Exception as e:
            raise gr.Error(f"Error creating map: {str(e)}")

    def plot_time_distribution(
        proc_state: ProcessorState,
        time_period: str,
        use_boxplot: bool,
        selected_classes_list,
        selected_recordings_list,
        date_range_start,
        date_range_end,
        time_start_hour,
        time_start_minute,
        time_end_hour,
        time_end_minute,
    ):
        """Creates time distribution plot with all filters applied."""
        if not proc_state or not proc_state.processor:
            raise gr.Error("Please load predictions first")
            
        if proc_state.class_thresholds is None:
            raise gr.Error("Class thresholds not initialized. Load data first.")
            
        # Validate thresholds from state
        validated_thresholds_df = proc_state.class_thresholds
            
        # Get data and apply all filters
        df = proc_state.processor.get_data()
        
        # Apply class and recording filters
        col_class = proc_state.processor.get_column_name("Class")
        conf_col = proc_state.processor.get_column_name("Confidence")
        if selected_classes_list:
            df = df[df[col_class].isin(selected_classes_list)]
        if selected_recordings_list:
            selected_recordings_list = [rec.lower() for rec in selected_recordings_list]
            df["recording_filename"] = df["recording_filename"].apply(
                lambda x: os.path.splitext(os.path.basename(x.strip()))[0].lower() 
                if isinstance(x, str) else x
            )
            df = df[df["recording_filename"].isin(selected_recordings_list)]
            
        # Apply class-specific confidence thresholds using validated thresholds
        df = apply_class_thresholds(df, validated_thresholds_df, col_class, conf_col)
        
        # Apply date and time filters
        df = apply_datetime_filters(
            df, 
            date_range_start, 
            date_range_end,
            time_start_hour,
            time_start_minute,
            time_end_hour,
            time_end_minute
        )
        
        if df.empty:
            raise gr.Error("No data matches the selected filters")
            
        # Create plotter and generate plot
        plotter = TimeDistributionPlotter(
            data=df,
            class_col=col_class
        )
        
        try:
            fig = plotter.plot_distribution(
                time_period=time_period,
                use_boxplot=use_boxplot,
                title=f"Species {'Boxplots' if use_boxplot else 'Counts'} by {time_period.capitalize()}"
            )
            return gr.update(value=fig, visible=True)
        except Exception as e:
            raise gr.Error(f"Error creating time distribution plot: {str(e)}")

    def get_selection_tables(directory):
        """Reads prediction txt files and metadata csv files from directory."""
        from pathlib import Path
        directory = Path(directory)
        files = list(directory.glob("*.txt")) + list(directory.glob("*.csv"))
        return files

    def download_threshold_template(proc_state: ProcessorState):
        """Saves the current threshold table as a JSON file template."""
        if not proc_state or proc_state.class_thresholds is None or proc_state.class_thresholds.empty:
            raise gr.Error("No thresholds available to save. Load data first.")
        
        try:
            thresholds_dict = {}
            for _, row in proc_state.class_thresholds.iterrows():
                thresholds_dict[row['Class']] = float(row['Threshold'])
            
            file_location = gu.save_file_dialog(
                state_key="viz-threshold-template",
                filetypes=("JSON (*.json)",),
                default_filename="threshold_template.json",
            )
            
            if file_location:
                with open(file_location, "w") as f:
                    json.dump(thresholds_dict, f, indent=4)
                
                gr.Info("Threshold template saved successfully")
        except Exception as e:
            print(f"Error saving threshold template: {e}")
            raise gr.Error(f"Error saving threshold template: {e}")

    def select_threshold_json_file(proc_state: ProcessorState):
        """Opens a file dialog to select a JSON threshold file and loads its contents."""
        if not proc_state or not proc_state.processor:
            gr.Warning("Processor not initialized. Load data first.")
            return proc_state, gr.update()
        
        try:
            # Call select_file - ensure filetypes is a tuple of strings
            file_path = gu.select_file(
                filetypes=('JSON files (*.json)', 'All files (*.*)'), # Corrected format
                state_key="viz-threshold-json"
            )
            
            if not file_path:
                # User canceled or no file selected (file_path is None or empty string)
                return proc_state, gr.update()
                
            # Ensure file_path is a string before opening
            if not isinstance(file_path, str):
                 # This case should ideally not happen if gu.select_file works correctly
                 raise TypeError(f"Expected a file path string, but got {type(file_path)}")

            with open(file_path, 'r') as f:
                json_data = json.load(f)

            if not isinstance(json_data, dict):
                raise ValueError("JSON content must be a dictionary (object).")

            if proc_state.class_thresholds is None or proc_state.class_thresholds.empty:
                gr.Warning("Class thresholds not initialized. Cannot update.")
                return proc_state, gr.update()

            updated_thresholds_df = proc_state.class_thresholds.copy()
            updated_thresholds_df.set_index('Class', inplace=True)

            loaded_count = 0
            warning_messages = []

            for cls, threshold in json_data.items():
                if not isinstance(cls, str):
                    warning_messages.append(f"Skipping non-string class key: {cls}")
                    continue
                if not isinstance(threshold, (int, float)):
                    warning_messages.append(f"Skipping non-numeric threshold for class '{cls}': {threshold}")
                    continue
                
                valid_threshold = float(threshold)
                clipped_threshold = max(0.01, min(0.99, valid_threshold))
                if clipped_threshold != valid_threshold:
                    warning_messages.append(f"Threshold for '{cls}' ({valid_threshold}) clipped to {clipped_threshold}.")
                    
                if cls in updated_thresholds_df.index:
                    updated_thresholds_df.loc[cls, 'Threshold'] = clipped_threshold
                    loaded_count += 1
                else:
                    warning_messages.append(f"Class '{cls}' from JSON not found in loaded data.")

            updated_thresholds_df.reset_index(inplace=True)

            if warning_messages:
                gr.Warning("\n".join(warning_messages))

            new_state = ProcessorState(
                processor=proc_state.processor,
                prediction_dir=proc_state.prediction_dir,
                metadata_dir=proc_state.metadata_dir,
                color_map=proc_state.color_map,
                class_thresholds=updated_thresholds_df
            )
            
            gr.Info(f"Successfully loaded thresholds for {loaded_count} classes from JSON.")
            return new_state, gr.update(value=updated_thresholds_df)
            
        except Exception as e:
            print(f"Error loading thresholds from JSON: {e}")
            gr.Error(f"Error loading thresholds from JSON: {str(e)}")
            return proc_state, gr.update()

    with gr.Tab(loc.localize("visualization-tab-title")):
        gr.Markdown(
            """
            <style>
            .custom-checkbox-group {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                grid-gap: 8px;
            </style>
            """
        )

        # States
        processor_state = gr.State()
        prediction_files_state = gr.State()
        metadata_files_state = gr.State()

        # File Selection UI
        with gr.Row():
            with gr.Column():
                prediction_select_directory_btn = gr.Button(loc.localize("eval-tab-prediction-selection-button-label"))
                prediction_directory_input = gr.Matrix(
                    interactive=False,
                    headers=[loc.localize("eval-tab-selections-column-file-header")],
                )
            with gr.Column():
                metadata_select_directory_btn = gr.Button(loc.localize("viz-tab-metadata-selection-button-label"))
                metadata_directory_input = gr.Matrix(
                    interactive=False,
                    headers=[loc.localize("eval-tab-selections-column-file-header")],
                )

        # Prediction columns box (using gr.Group as in evaluation tab)
        with gr.Group(visible=False) as prediction_group:
            with gr.Accordion(loc.localize("eval-tab-prediction-col-accordion-label"), open=True):
                with gr.Row():
                    prediction_columns: dict[str, gr.Dropdown] = {}
                    for col in ["Start Time", "End Time", "Class", "Confidence", "Recording", "Correctness"]:
                        prediction_columns[col] = gr.Dropdown(choices=[], label=localized_column_labels.get(col, col))

        # Metadata columns box
        with gr.Group(visible=False) as metadata_group:
            with gr.Accordion(loc.localize("viz-tab-metadata-col-accordion-label"), open=True):
                with gr.Row():
                    metadata_columns: dict[str, gr.Dropdown] = {}
                    for col in ["Site", "X", "Y"]:
                        label = localized_column_labels[col]
                        if col == "X":
                            label += " (Decimal Degrees)"
                        elif col == "Y":
                            label += " (Decimal Degrees)"
                        metadata_columns[col] = gr.Dropdown(choices=[], label=label)

        # Class and Recording Selection Box
        with gr.Group(visible=True) as class_recording_group:
            with gr.Accordion(loc.localize("viz-tab-class-recording-accordion-label"), open=False):
                with gr.Row():
                    with gr.Column():
                        select_classes_checkboxgroup = gr.CheckboxGroup(
                            choices=[],
                            value=[],
                            label=loc.localize("viz-tab-classes-label"),
                            info=loc.localize("viz-tab-classes-info"),
                            interactive=True,
                            elem_classes="custom-checkbox-group",
                        )
                    with gr.Column():
                        select_recordings_checkboxgroup = gr.CheckboxGroup(
                            choices=[],
                            value=[],
                            label=loc.localize("viz-tab-recordings-label"),
                            info=loc.localize("viz-tab-recordings-info"),
                            interactive=True,
                            elem_classes="custom-checkbox-group",
                        )

        # Parameters Box
        with gr.Group():
            with gr.Accordion(loc.localize("viz-tab-parameters-accordion-label"), open=False):
                with gr.Row():
                    date_range_start = gr.DateTime(
                        label=loc.localize("viz-tab-date-range-start-label"),
                        info=loc.localize("viz-tab-date-range-start-info"),
                        interactive=True,
                        show_label=True,
                        include_time=False
                    )
                    date_range_end = gr.DateTime(
                        label=loc.localize("viz-tab-date-range-end-label"),
                        info=loc.localize("viz-tab-date-range-end-info"),
                        interactive=True,
                        show_label=True,
                        include_time=False
                    )

                with gr.Row():
                    with gr.Column():
                        with gr.Row():
                            time_start_hour = gr.Dropdown(
                                choices=[f"{i:02d}" for i in range(24)],
                                value="00",
                                label=loc.localize("viz-tab-start-time-label-hour"),
                                interactive=True
                            )
                            time_start_minute = gr.Dropdown(
                                choices=[f"{i:02d}" for i in range(60)],
                                value="00",
                                label=loc.localize("viz-tab-start-time-label-minute"),
                                interactive=True
                            )
                    
                    with gr.Column(): 
                        with gr.Row():
                            time_end_hour = gr.Dropdown(
                                choices=[f"{i:02d}" for i in range(24)],
                                value="23",
                                label=loc.localize("viz-tab-end-time-label-hour"),
                                interactive=True
                            )
                            time_end_minute = gr.Dropdown(
                                choices=[f"{i:02d}" for i in range(60)],
                                value="59",
                                label=loc.localize("viz-tab-end-time-label-minute"),
                                interactive=True
                            )

                with gr.Row():
                    time_distribution_period = gr.Dropdown(
                        choices=["hour", "day", "month", "year"],
                        value="hour",
                        label="Time Distribution Period",
                        info="Select period for time distribution plot"
                    )
                    use_boxplot = gr.Checkbox(
                        label="Use Box Plots",
                        info="Show distribution as box plots instead of counts",
                        value=False
                    )
                
                # Threshold components 
                with gr.Row():
                     class_thresholds_df = gr.DataFrame(
                         headers=["Class", "Threshold"],
                         datatype=["str", "number"],
                         label="Class Confidence Thresholds (Read-only)",
                         interactive=False, # Make DataFrame read-only
                         visible=False,
                         col_count=(2, "fixed")
                     )
                # Replace JSON Upload with Select JSON button and add Download button
                with gr.Row():
                    threshold_json_select_btn = gr.Button(
                        "Select Threshold JSON File",
                        variant="secondary",
                        visible=False,
                        scale=2
                    )
                    threshold_template_download_btn = gr.Button(
                        "Download Threshold Template",
                        variant="secondary",
                        visible=False,
                        scale=2
                    )

                # Add correctness mode selection
                correctness_mode = gr.Radio(
                    choices=[
                        "Ignore correctness flags",
                        "Show only correct",
                        "Show only incorrect",
                        "Show only unspecified",
                        "Distinguish all"
                    ],
                    value="Ignore correctness flags",
                    label="Correctness Filter Mode",
                    info="Select how to handle the correctness flags in visualizations",
                    interactive=True
                )

        # Warning message about model validation and interpretation
        gr.Markdown(
            """
            <div style="background-color: #FFF3CD; color: #856404; padding: 10px; margin: 10px 0; 
                      border-left: 5px solid #FFDD33; border-radius: 4px;">
              <span style="font-weight: bold;">⚠️ Warning:</span> Visualizations should be interpreted with caution. 
              Please verify model performance for your target species and environment before drawing conclusions. 
              Confidence thresholds significantly affect detection rates - lower values increase detections but may 
              introduce false positives. Temporal and spatial patterns may reflect recording methods rather than 
              actual species behavior.
            </div>
            """
        )

        # Action button and output for smooth distribution plot
        plot_predictions_btn = gr.Button(
            loc.localize("viz-tab-plot-distributions-button-label"), 
            variant="huggingface"
        )
        smooth_distribution_output = gr.Plot(label=loc.localize("viz-tab-distribution-plot-label"), visible=False)

        # Add map button and output after the existing plot components
        plot_map_btn = gr.Button(
            loc.localize("viz-tab-plot-map-button-label"), 
            variant="huggingface"
        )
        map_output = gr.Plot(label=loc.localize("viz-tab-map-plot-label"), visible=False)

        # Add plot time distribution button after existing plot buttons
        plot_time_distribution_btn = gr.Button(
            "Plot Time Distribution", 
            variant="huggingface"
        )
        time_distribution_output = gr.Plot(
            label="Time Distribution Plot",
            visible=False
        )
        
        # Add temporal scatter plot button and output
        plot_temporal_scatter_btn = gr.Button(
            "Plot Temporal Scatter", 
            variant="huggingface"
        )
        temporal_scatter_output = gr.Plot(
            label="Temporal Scatter Plot",
            visible=False
        )

        # Add calculate detections button and output table
        calculate_detections_btn = gr.Button(
            "Calculate Detections", 
            variant="huggingface"
        )
        detections_table = gr.DataFrame(
            show_label=False,
            type="pandas",
            visible=False,
            interactive=False,
            wrap=True,  # Enable text wrapping for better readability
            column_widths=[200, 110, 80, 130, 90, 150, 110, 110, 80]  # Set widths for all columns
        )

        # Interactions
        def get_selection_func(state_key, on_select):
            def select_directory_on_empty():
                folder = gu.select_folder(state_key=state_key)
                if folder:
                    files = get_selection_tables(folder)
                    files_to_display = files[:100] + [["..."]] if len(files) > 100 else files
                    return [files, files_to_display, gr.update(visible=True)] + on_select(files)
                return ["", [[loc.localize("eval-tab-no-files-found")]], gr.update(visible=False)] + [gr.update(visible=False)] * 6
            return select_directory_on_empty

        prediction_select_directory_btn.click(
            get_selection_func("eval-predictions-dir", update_prediction_columns),
            outputs=[prediction_files_state, prediction_directory_input, prediction_group]
            + [prediction_columns[label] for label in ["Start Time", "End Time", "Class", "Confidence", "Recording", "Correctness"]],
            show_progress=True,
        )

        metadata_select_directory_btn.click(
            get_selection_func("viz-metadata-dir", update_metadata_columns),
            outputs=[
                metadata_files_state,
                metadata_directory_input,
                metadata_group,
                metadata_columns["Site"],
                metadata_columns["X"],
                metadata_columns["Y"]
            ],
            show_progress=True,
        )

        # Add visibility toggle for metadata group
        metadata_directory_input.change(
            lambda x: gr.update(visible=bool(x)),
            inputs=[metadata_files_state],
            outputs=[metadata_group],
        )

        # Update processor and selections when columns change or files change
        # Consolidate triggers for update_selections
        update_triggers = [
            prediction_files_state,
            metadata_files_state,
            prediction_columns["Start Time"],
            prediction_columns["End Time"],
            prediction_columns["Class"],
            prediction_columns["Confidence"],
            prediction_columns["Recording"],
            prediction_columns["Correctness"],
            metadata_columns["Site"],
            metadata_columns["X"],
            metadata_columns["Y"],
        ]

        for trigger in update_triggers:
            trigger.change(
                fn=update_selections,
                inputs=[
                    prediction_files_state,
                    metadata_files_state,
                    prediction_columns["Start Time"],
                    prediction_columns["End Time"],
                    prediction_columns["Class"],
                    prediction_columns["Confidence"],
                    prediction_columns["Recording"],
                    prediction_columns["Correctness"],
                    metadata_columns["Site"],
                    metadata_columns["X"],
                    metadata_columns["Y"],
                    select_classes_checkboxgroup, # Pass current selections
                    select_recordings_checkboxgroup, # Pass current selections
                ],
                outputs=[
                    select_classes_checkboxgroup,
                    select_recordings_checkboxgroup,
                    processor_state,
                    class_thresholds_df, # Output to update the DataFrame UI
                    threshold_json_select_btn, # Update for JSON select button
                    threshold_template_download_btn # Update for download button
                ],
                # Trigger date updates only on success of processor update
            ).success(
                fn=update_datetime_defaults,
                inputs=[processor_state],
                outputs=[
                    date_range_start,
                    date_range_end,
                    time_start_hour,
                    time_start_minute,
                    time_end_hour,
                    time_end_minute
                ]
            )

        # Add click handlers for the new buttons
        threshold_json_select_btn.click(
            fn=select_threshold_json_file,
            inputs=[processor_state],
            outputs=[processor_state, class_thresholds_df],
            api_name="select_threshold_json" # Add unique API name for better traceability
        )
        
        threshold_template_download_btn.click(
            fn=download_threshold_template,
            inputs=[processor_state]
        )

        # Plot button action (Histogram - ignores class thresholds)
        plot_predictions_btn.click(
            fn=plot_predictions_action,
            inputs=[
                processor_state,
                select_classes_checkboxgroup,
                select_recordings_checkboxgroup,
                date_range_start,
                date_range_end,
                time_start_hour,
                time_start_minute,
                time_end_hour,
                time_end_minute,
            ],
            outputs=[processor_state, smooth_distribution_output]
        )

        # Add click handler for map button (Uses class thresholds from state)
        plot_map_btn.click(
            fn=plot_spatial_distribution,
            inputs=[
                processor_state,
                metadata_columns["X"],
                metadata_columns["Y"],
                metadata_columns["Site"],
                date_range_start,
                date_range_end,
                time_start_hour,
                time_start_minute,
                time_end_hour,
                time_end_minute,
            ],
            outputs=[processor_state, map_output]
        )

        # Add click handler for time distribution button (Uses class thresholds from state)
        plot_time_distribution_btn.click(
            fn=plot_time_distribution,
            inputs=[
                processor_state,
                time_distribution_period,
                use_boxplot,
                select_classes_checkboxgroup,
                select_recordings_checkboxgroup,
                date_range_start,
                date_range_end,
                time_start_hour,
                time_start_minute,
                time_end_hour,
                time_end_minute,
            ],
            outputs=[time_distribution_output]
        )
        
        # Add click handler for temporal scatter button
        plot_temporal_scatter_btn.click(
            fn=plot_temporal_scatter,
            inputs=[
                processor_state,
                select_classes_checkboxgroup,
                select_recordings_checkboxgroup,
                date_range_start,
                date_range_end,
                time_start_hour,
                time_start_minute,
                time_end_hour,
                time_end_minute,
                metadata_columns["X"],
                metadata_columns["Y"],
                correctness_mode,  # Add correctness_mode input
            ],
            outputs=[processor_state, temporal_scatter_output]
        )

        # Handler function for calculate detections button (Uses class thresholds from state)
        def calculate_detection_counts(
            proc_state: ProcessorState,
            selected_classes_list,
            selected_recordings_list,
            date_range_start,
            date_range_end,
            time_start_hour,
            time_start_minute,
            time_end_hour,
            time_end_minute,
            correctness_mode,  # Add correctness_mode parameter
        ):
            """Count detections for each class with the applied filters."""
            if not proc_state or not proc_state.processor:
                raise gr.Error("Please load predictions first")
                
            # Correctly check if thresholds DataFrame is None or empty
            if proc_state.class_thresholds is None or proc_state.class_thresholds.empty:
                raise gr.Error("Class thresholds not initialized or are empty. Load data and optionally JSON thresholds first.")
                
            # Validate thresholds from state
            validated_thresholds_df = proc_state.class_thresholds
                
            # Get data and apply filters
            df = proc_state.processor.get_data()
            if df.empty:
                raise gr.Error("No predictions to analyze")
                
            # Apply class and recording filters
            col_class = proc_state.processor.get_column_name("Class")
            conf_col = proc_state.processor.get_column_name("Confidence")
            corr_col = proc_state.processor.get_column_name("Correctness")
            
            # Debug which correctness column is being used
            print(f"Using correctness column: '{corr_col}'")
            print(f"Available columns: {df.columns.tolist()}")
            
            # Check if correctness column exists; if not, try both capitalization forms
            if corr_col not in df.columns:
                # Try both 'correctness' and 'Correctness'
                alt_corr_col = 'correctness' if corr_col == 'Correctness' else 'Correctness'
                if alt_corr_col in df.columns:
                    print(f"Switching to alternative correctness column: '{alt_corr_col}'")
                    corr_col = alt_corr_col
                else:
                    # Create an empty correctness column if none exists
                    print(f"No correctness column found, creating a placeholder")
                    df[corr_col] = None
            
            if selected_classes_list:
                df = df[df[col_class].isin(selected_classes_list)]
                
            if selected_recordings_list:
                selected_recordings_list = [rec.lower() for rec in selected_recordings_list]
                df["recording_filename"] = df["recording_filename"].apply(
                    lambda x: os.path.splitext(os.path.basename(x.strip()))[0].lower() 
                    if isinstance(x, str) else x
                )
                df = df[df["recording_filename"].isin(selected_recordings_list)]
                
            # Apply class-specific confidence thresholds using validated thresholds
            df = apply_class_thresholds(df, validated_thresholds_df, col_class, conf_col)
            
            # Apply date and time filters
            df = apply_datetime_filters(
                df, 
                date_range_start, 
                date_range_end,
                time_start_hour,
                time_start_minute,
                time_end_hour,
                time_end_minute
            )
            
            # Log count before filtering
            print(f"Records before correctness filter: {len(df)}")
            print(f"Correctness mode: {correctness_mode}")
            
            # Make sure corr_col has proper boolean values (not strings)
            if corr_col in df.columns:
                # Convert string 'true'/'false' to proper boolean
                df[corr_col] = df[corr_col].map({
                    'true': True, 'True': True, True: True, 1: True,
                    'false': False, 'False': False, False: False, 0: False,
                    'nan': None, 'none': None, '': None, 'null': None
                }, na_action='ignore')
            
            # Apply correctness filter based on selected mode
            if correctness_mode == "Show only correct":
                df = df[(df[corr_col] == True) | (df[corr_col] == 'True')]
                print(f"Records after filtering for correct: {len(df)}")
            elif correctness_mode == "Show only incorrect":
                df = df[(df[corr_col] == False) | (df[corr_col] == 'False')]
                print(f"Records after filtering for incorrect: {len(df)}")
            elif correctness_mode == "Show only unspecified":
                df = df[(df[corr_col].isna()) | (df[corr_col] == '') | (df[corr_col] == 'nan')]
                print(f"Records after filtering for unspecified: {len(df)}")
            # "Ignore correctness flags" and "Distinguish all" modes don't filter the data
            
            if df.empty:
                raise gr.Error("No data matches the selected filters")
                
            # Handle the distinction between modes for counting
            if correctness_mode == "Distinguish all":
                # Create a human-readable correctness column for display
                df['correctness_display'] = df[corr_col].apply(
                    lambda x: "Correct" if x == True else "Incorrect" if x == False else "Unspecified"
                )
                
                # Get all unique classes
                classes = df[col_class].unique()
                
                # Create a new DataFrame for results with one row per species
                result_rows = []
                
                # Calculate the total number of detections
                total_detections = len(df)
                
                # For each class, calculate counts by correctness value
                for cls in classes:
                    class_df = df[df[col_class] == cls]
                    
                    # Count by correctness
                    correct_count = sum(class_df['correctness_display'] == "Correct")
                    incorrect_count = sum(class_df['correctness_display'] == "Incorrect")
                    unspecified_count = sum(class_df['correctness_display'] == "Unspecified")
                    total_count = len(class_df)
                    
                    # Calculate percentages of total detections
                    correct_pct = f"{(correct_count / total_detections * 100):.1f}%" if total_detections else "0.0%"
                    incorrect_pct = f"{(incorrect_count / total_detections * 100):.1f}%" if total_detections else "0.0%"
                    unspecified_pct = f"{(unspecified_count / total_detections * 100):.1f}%" if total_detections else "0.0%"
                    total_pct = f"{(total_count / total_detections * 100):.1f}%" if total_detections else "0.0%"
                    
                    # Add row for this class
                    result_rows.append({
                        "Species": cls,
                        "Correct Count": correct_count,
                        "Correct %": correct_pct,
                        "Incorrect Count": incorrect_count,
                        "Incorrect %": incorrect_pct,
                        "Unspecified Count": unspecified_count,
                        "Unspecified %": unspecified_pct,
                        "Total Count": total_count,
                        "Total %": total_pct,
                    })
                
                # Create DataFrame and sort by total count (descending)
                result_df = pd.DataFrame(result_rows)
                result_df = result_df.sort_values("Total Count", ascending=False)
                
                # Calculate grand totals
                correct_total = sum(df['correctness_display'] == "Correct")
                incorrect_total = sum(df['correctness_display'] == "Incorrect")
                unspecified_total = sum(df['correctness_display'] == "Unspecified")
                
                # Add grand total row
                grand_total = {
                    "Species": "Grand Total",
                    "Correct Count": correct_total,
                    "Correct %": f"{(correct_total / total_detections * 100):.1f}%" if total_detections else "0.0%",
                    "Incorrect Count": incorrect_total,
                    "Incorrect %": f"{(incorrect_total / total_detections * 100):.1f}%" if total_detections else "0.0%",
                    "Unspecified Count": unspecified_total,
                    "Unspecified %": f"{(unspecified_total / total_detections * 100):.1f}%" if total_detections else "0.0%",
                    "Total Count": total_detections,
                    "Total %": "100.0%",
                }
                
                # Concatenate with the grand total row
                result_df = pd.concat([result_df, pd.DataFrame([grand_total])], ignore_index=True)
                
                # Organize columns 
                column_order = [
                    "Species", 
                    "Correct Count", "Correct %",
                    "Incorrect Count", "Incorrect %", 
                    "Unspecified Count", "Unspecified %",
                    "Total Count", "Total %"
                ]
                result_df = result_df[column_order]
                
            else:
                # Standard counting logic for other modes (no distinction by correctness)
                class_counts = df[col_class].value_counts().reset_index()
                class_counts.columns = ["Species", "Count"]
                
                # Add percentage column
                total = class_counts["Count"].sum()
                class_counts["Percentage"] = (class_counts["Count"] / total * 100).round(1).astype(str) + "%"
                
                # Sort by detection count (descending)
                class_counts = class_counts.sort_values("Count", ascending=False)
                
                # Add total row
                total_row = pd.DataFrame({
                    "Species": ["Total"],
                    "Count": [total],
                    "Percentage": ["100.0%"]
                })
                
                result_df = pd.concat([class_counts, total_row])
            
            # Set column widths for better display
            column_widths = {
                "Species": "200px",
                "Count": "110px",
                "Percentage": "110px",
                "Correct Count": "110px", 
                "Correct %": "80px",
                "Incorrect Count": "130px", 
                "Incorrect %": "90px",
                "Unspecified Count": "150px", 
                "Unspecified %": "110px",
                "Total Count": "110px", 
                "Total %": "80px"
            }
            
            return gr.update(
                value=result_df, 
                visible=True, 
                column_widths=[column_widths.get(col, "120px") for col in result_df.columns]
            )

        # Add click handler for calculate detections button
        calculate_detections_btn.click(
            fn=calculate_detection_counts,
            inputs=[
                processor_state,
                select_classes_checkboxgroup,
                select_recordings_checkboxgroup,
                date_range_start,
                date_range_end,
                time_start_hour,
                time_start_minute,
                time_end_hour,
                time_end_minute,
                correctness_mode,  # Add correctness_mode input
            ],
            outputs=[detections_table]
        )


if __name__ == "__main__":
    gu.open_window(build_visualization_tab)
