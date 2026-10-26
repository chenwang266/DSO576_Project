import plotly.graph_objects as go
from src.pricing import histogram


def price_histogram(prices, median):
    bins = histogram(prices)
    figure = go.Figure()
    if not bins.empty:
        figure.add_bar(x=(bins.left + bins.right) / 2, y=bins['count'],
            width=bins.right - bins.left, marker_color='#1c766e', name='Eligible listings')
        figure.add_vline(x=float(median), line_dash='dash', line_color='#b06c22', annotation_text='Median')
    figure.update_layout(title='Observed advertised prices', xaxis_title='USD',
        yaxis_title='Listings', template='plotly_white', bargap=.03, height=340)
    return figure
