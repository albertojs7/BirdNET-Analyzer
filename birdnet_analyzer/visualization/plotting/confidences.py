import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import gaussian_kde
from typing import List, Optional, Dict


class ConfidencePlotter:
    """
    A helper class to plot distribution (ridgeline or stacked) plots of confidence scores
    for each class using only matplotlib and plotly.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        class_col: str = "class",
        conf_col: str = "confidence"
    ):
        """
        Initialize the ConfidencePlotter with a DataFrame and column names.

        Args:
            data (pd.DataFrame): Data containing confidence scores and class labels.
            class_col (str): Name of the column that indicates class/species/label.
            conf_col (str): Name of the column that indicates confidence score.
        """
        self.data = data.copy()
        self.class_col = class_col
        self.conf_col = conf_col

        # Ensure these columns exist
        if self.class_col not in self.data.columns:
            raise ValueError(f"Column '{self.class_col}' not found in data.")
        if self.conf_col not in self.data.columns:
            raise ValueError(f"Column '{self.conf_col}' not found in data.")

        # Gather unique classes
        self.classes = sorted(self.data[self.class_col].dropna().unique())

    def _get_color_map(self, classes: List[str]) -> Dict[str, str]:
        """Create consistent color mapping for classes."""
        base_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink']
        colors = base_colors * (1 + len(classes) // len(base_colors))
        return {cls: colors[i] for i, cls in enumerate(sorted(classes))}

    def plot_ridgeline_matplotlib(
        self,
        figsize=(6, 8),
        bandwidth=0.1,
        overlap=0.6,
        fill=True,
        alpha=0.6,
        cmap="Spectral_r",
        title="Ridgeline Plot of Confidence Scores"
    ):
        """
        Creates a ridgeline plot using matplotlib and scipy's gaussian_kde for each class.

        Args:
            figsize (tuple): Figure size (width, height).
            bandwidth (float): Optional bandwidth scaling for KDE smoothing. 
                               This can be adjusted if the default smoothing is too coarse or too fine.
            overlap (float): Vertical overlap between consecutive distributions (0->none, 1->complete).
            fill (bool): Whether to fill under the KDE curve.
            alpha (float): Transparency of the fill/line.
            cmap (str): Colormap name for the ridgeline gradient.
            title (str): Title for the entire figure.
        """
        # Prepare figure
        fig, ax = plt.subplots(figsize=figsize)

        # Choose a colormap
        cm = plt.get_cmap(cmap)
        num_classes = len(self.classes)

        # For vertical spacing, let's define a y‑offset for each class
        # We'll plot from top to bottom
        y_offsets = np.linspace(0, -(num_classes-1)*overlap, num_classes)

        # Plot each class
        for i, cls in enumerate(self.classes):
            cls_data = self.data.loc[self.data[self.class_col] == cls, self.conf_col].dropna().values
            if len(cls_data) < 2:
                # We need at least 2 points for a KDE
                continue

            # Compute Gaussian KDE
            kde = gaussian_kde(cls_data)
            if bandwidth:
                # Adjust the covariance factor if a bandwidth is given
                kde.set_bandwidth(bw_method=kde.factor * bandwidth)

            # Evaluate KDE on a grid from min to max
            x_min, x_max = cls_data.min(), cls_data.max()
            x_grid = np.linspace(x_min, x_max, 200)
            y_grid = kde.evaluate(x_grid)

            # Vertical offset for the ridgeline
            y_offset = y_offsets[i]
            color = cm(i / num_classes)

            if fill:
                ax.fill_between(
                    x_grid,
                    y_offset,
                    y_grid + y_offset,
                    color=color,
                    alpha=alpha
                )
            ax.plot(
                x_grid,
                y_grid + y_offset,
                color=color,
                alpha=alpha,
                label=cls if i == 0 else None  # only label once if desired
            )

            # Label for each class on the left side
            ax.text(
                x_min,
                y_offset + 0.02,
                cls,
                ha="right",
                va="bottom",
                fontsize=9
            )

        ax.set_yticks([])
        ax.set_ylabel("")
        ax.set_xlabel("Confidence Score")
        ax.set_title(title)
        plt.tight_layout()
        plt.show()

    def plot_histogram_matplotlib(
        self,
        bins: int = 30,
        smooth: bool = False,
        alpha: float = 0.6,
        title: str = "Histogram of Confidence Scores by Class",
        figsize: tuple = (6, 8)
    ):
        """
        Creates a per-class histogram plot using matplotlib.
        One histogram is plotted for each class with vertical offsets.
        If smooth is True, the histogram counts are smoothed via convolution.
        The style (colors, transparency, labeling) matches that of the KDE/ridgeline plot.
        """
        fig, ax = plt.subplots(figsize=figsize)
        cm = plt.get_cmap("Spectral_r")
        num_classes = len(self.classes)
        # Define vertical offsets (similar to ridgeline)
        y_offsets = np.linspace(0, -(num_classes - 1) * 0.6, num_classes)
        
        for i, cls in enumerate(self.classes):
            cls_data = self.data.loc[self.data[self.class_col] == cls, self.conf_col].dropna().values
            if len(cls_data) < 1:
                continue
            # Compute histogram normalized to density
            counts, bin_edges = np.histogram(cls_data, bins=bins, density=True)
            # Compute center values for bins
            x_vals = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            # Optionally smooth the counts using a simple moving average
            if smooth:
                window = np.ones(5) / 5
                counts = np.convolve(counts, window, mode="same")
            y_offset = y_offsets[i]
            color = cm(i / num_classes)
            ax.fill_between(x_vals, y_offset, counts + y_offset, color=color, alpha=alpha)
            ax.plot(x_vals, counts + y_offset, color=color, alpha=alpha)
            # Label the left side with class name
            ax.text(bin_edges[0], y_offset + 0.02, cls, ha="right", va="bottom", fontsize=9)
        
        ax.set_yticks([])
        ax.set_ylabel("")
        ax.set_xlabel("Confidence Score")
        ax.set_title(title)
        plt.tight_layout()
        plt.show()
        return fig

    def plot_histogram_plotly(
        self,
        title: str = "Histogram of Confidence Scores by Class"
    ) -> go.Figure:
        """
        Creates a per-class histogram plot using Plotly.
        Each class is plotted as a grouped bar chart using exactly 10 bins.
        Each bin represents a 0.1-width range of confidence scores.
        """
        if self.data.empty:
            raise ValueError("No data to plot")
        
        # Set up confidence bins (10 bins from 0 to 1)
        x_title = 'Confidence Score'
        bin_edges = np.linspace(0, 1, 11)  # 11 edges for 10 bins: 0, 0.1, 0.2, ..., 1.0
        bin_labels = [f"≤ {edge:.1f}" for edge in bin_edges[1:]]  # 0.1, 0.2, ..., 1.0
        
        # Create figure
        fig = go.Figure()
        classes = sorted(self.data[self.class_col].unique())
        color_map = self._get_color_map(classes)
        
        # Plot histogram for each class
        for cls in classes:
            cls_data = self.data[self.data[self.class_col] == cls]
            
            # Skip empty classes
            if cls_data.empty:
                continue
            
            # Calculate histogram
            counts, _ = np.histogram(cls_data[self.conf_col].dropna(), bins=bin_edges)
            
            # Add bar trace
            fig.add_trace(go.Bar(
                name=str(cls),
                x=bin_labels,
                y=counts,
                marker_color=color_map.get(cls),
                opacity=0.6,
                hovertemplate=(
                    "Bin: %{x}<br>"
                    "Species: " + str(cls) + "<br>"
                    "Count: %{y}<br>"
                    "<extra></extra>"
                )
            ))
        
        # Update layout - exactly matching the TimeDistributionPlotter layout
        fig.update_layout(
            barmode='group',
            title=title,
            xaxis_title=x_title,
            yaxis_title='Count',
            legend_title='Species',
            legend=dict(x=1.02, y=1),
            margin=dict(r=150),
            showlegend=True
        )
        
        return fig

    def plot_smooth_distribution_plotly(
        self,
        bandwidth: float = 0.2,
        title: str = "Smooth Distribution of Confidence Scores",
        classes: List[str] = None,
        color_map: Dict[str, str] = None
    ) -> go.Figure:
        """
        Creates a smooth distribution plot using plotly.

        Args:
            bandwidth: Width of the smoothing window
            title: Plot title
            classes: List of classes to plot (defaults to all)
            color_map: Dict mapping class names to colors
        """
        if not classes:
            classes = sorted(self.data[self.class_col].unique())
            
        fig = go.Figure()
        dash_patterns = ['solid', 'dash', 'dot', 'dashdot', 'longdash', 'longdashdot']

        for i, class_name in enumerate(classes):
            class_data = self.data[self.data[self.class_col] == class_name][self.conf_col].dropna()
            if len(class_data) < 2:
                continue
                
            kde = gaussian_kde(class_data, bw_method=bandwidth)
            x_range = np.linspace(class_data.min(), class_data.max(), 200)
            y_values = kde(x_range)
            
            color = color_map.get(class_name) if color_map else None
            fig.add_trace(
                go.Scatter(
                    x=x_range,
                    y=y_values,
                    mode="lines",
                    fill="tozeroy",
                    name=str(class_name),
                    line=dict(
                        color=color,
                        dash=dash_patterns[i % len(dash_patterns)]
                    )
                )
            )

        if len(fig.data) == 0:
            raise ValueError("Not enough data points for any of the selected classes.")

        fig.update_layout(
            title=title,
            xaxis_title="Confidence Score",
            yaxis_title="Estimated Density",
            legend_title="Class",
            legend=dict(x=1.02, y=1),
            margin=dict(r=150)  # add right margin for legend
        )
        
        return fig
