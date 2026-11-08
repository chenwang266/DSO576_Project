"""Customer-facing Plotly views of existing backend evidence; no ranking formulas."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .pricing import histogram

LOCAL = '#087f8c'
PEER = '#496aa3'
AMBER = '#bc701c'
GRAY = '#dce4ed'
COLORS = {'Persistent premium':AMBER,'Persistent discount':LOCAL,'Reversed':'#8666ad','Neutral':'#7c8b99','Insufficient evidence':'#c4ccd5'}
PERIODS = [('march','March'),('june','June')]
CONTEXT_LABELS = [('availability_90','Available days · next 90 days','Days'),('reviews_ltm','Reviews · last 12 months','Reviews'),('value_score','Review value · 0–5','Score'),('minimum_nights','Minimum stay requirement','Nights')]

def base(fig, height=340):
    fig.update_layout(height=height,template='plotly_white',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Arial, sans-serif',color='#284056',size=12),margin=dict(l=15,r=25,t=40,b=35),legend=dict(orientation='h',y=1.13,x=0),hoverlabel=dict(bgcolor='white'))
    fig.update_xaxes(showgrid=False,zeroline=False)
    fig.update_yaxes(gridcolor='#e5ebf1',zeroline=False)
    return fig

def empty(message='No qualifying evidence under these filters.'):
    fig=base(go.Figure())
    fig.add_annotation(text=message,x=.5,y=.5,xref='paper',yref='paper',showarrow=False,font_size=14)
    fig.update_xaxes(visible=False);fig.update_yaxes(visible=False)
    return fig

def distribution(values, median):
    bins=histogram(values)
    if bins.empty:return empty('No valid positive prices for this segment.')
    fig=go.Figure(go.Bar(x=(bins.left+bins.right)/2,y=bins['count'],width=(bins.right-bins.left)*.94,marker_color=LOCAL,customdata=bins[['left','right']].values,hovertemplate='$%{customdata[0]:,.2f}–$%{customdata[1]:,.2f}<br>%{y} listings<extra></extra>'))
    fig.add_vline(x=float(median),line_dash='dash',line_color=AMBER,annotation_text=f'Median ${median:,.2f}')
    base(fig);fig.update_layout(xaxis_title='Advertised price (USD) · full range',yaxis_title='Priced listings')
    return fig

def price_band(row, period):
    fig=go.Figure()
    for prefix,name,color,y in [('', 'This segment',LOCAL,1),('peer_','LA peer',PEER,0)]:
        median=row.get(f'{prefix}median_price_usd_{period}')
        q1=row.get(f'{prefix}p25_price_usd_{period}');q3=row.get(f'{prefix}p75_price_usd_{period}')
        if pd.notna(median):
            if pd.notna(q1) and pd.notna(q3):
                fig.add_trace(go.Scatter(x=[q1,q3],y=[y,y],mode='lines',line=dict(color=color,width=14),opacity=.25,showlegend=False,hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=[median],y=[y],mode='markers+text',text=[f'${median:,.2f}'],textposition='top center',textfont=dict(color=color),marker=dict(color=color,size=13,symbol='diamond'),name=name,customdata=[[q1,q3,row.get(f'{prefix}priced_rows_{period}')]],hovertemplate='Median $%{x:,.2f}<br>P25 $%{customdata[0]:,.2f} · P75 $%{customdata[1]:,.2f}<br>Valid prices: %{customdata[2]:,.0f}<extra>%{fullData.name}</extra>'))
    if not fig.data:return empty('Price benchmark is unavailable.')
    base(fig);fig.update_layout(showlegend=False,xaxis_title='USD · band = middle 50% of advertised prices',yaxis=dict(tickmode='array',tickvals=[0,1],ticktext=['LA peer','This segment'],range=[-.55,1.6],showgrid=False),xaxis_tickprefix='$')
    return fig

def price_comparison(row):
    fig=go.Figure()
    for prefix,name,color in [('', 'This segment',LOCAL),('peer_','LA peer · includes local',PEER)]:
        values=[row.get(f'{prefix}median_price_usd_{d}') for d,_ in PERIODS]
        q1=[row.get(f'{prefix}p25_price_usd_{d}') for d,_ in PERIODS]
        q3=[row.get(f'{prefix}p75_price_usd_{d}') for d,_ in PERIODS]
        plus=[q-m if pd.notna(q) and pd.notna(m) else None for q,m in zip(q3,values)]
        minus=[m-q if pd.notna(q) and pd.notna(m) else None for q,m in zip(q1,values)]
        fig.add_trace(go.Scatter(x=['March','June'],y=values,mode='lines+markers',name=name,line=dict(color=color,width=3),marker_size=10,connectgaps=False,error_y=dict(type='data',symmetric=False,array=plus,arrayminus=minus,color=color,thickness=2,width=7),customdata=list(zip(q1,q3)),hovertemplate='%{x}<br>Median $%{y:,.2f}<br>P25 $%{customdata[0]:,.2f} · P75 $%{customdata[1]:,.2f}<extra>%{fullData.name}</extra>'))
    base(fig,370);fig.update_layout(yaxis_title='Median advertised price (USD)',yaxis_tickprefix='$')
    return fig

def premium_comparison(row):
    values=[row.get(f'premium_pct_{d}') for d,_ in PERIODS]
    if all(pd.isna(v) for v in values):return empty('Premium unavailable: evidence minimum is not met.')
    fig=go.Figure(go.Bar(x=[v if pd.notna(v) else None for v in values],y=['March','June'],orientation='h',marker_color=[AMBER if pd.notna(v) and v>0 else LOCAL for v in values],text=[f'{v:+.1f}%' if pd.notna(v) else 'Unavailable' for v in values],textposition='outside',cliponaxis=False,hovertemplate='%{y}: %{x:+.1f}%<extra></extra>'))
    fig.add_vline(x=0,line_color='#6e8295',line_width=1)
    lo=min([0]+[float(v) for v in values if pd.notna(v)]);hi=max([0]+[float(v) for v in values if pd.notna(v)]);pad=max((hi-lo)*.22,1)
    base(fig,370);fig.update_layout(xaxis_range=[lo-pad,hi+pad],xaxis_title='Relative to same-date LA peer (%)',xaxis_ticksuffix='%',yaxis=dict(autorange='reversed',showgrid=False),showlegend=False)
    return fig

def context_comparison(row, period=None):
    periods=[(period,dict(PERIODS)[period])] if period else PERIODS
    fig=make_subplots(rows=2,cols=2,subplot_titles=[item[1] for item in CONTEXT_LABELS],vertical_spacing=.29,horizontal_spacing=.19)
    for index,(metric,_,unit) in enumerate(CONTEXT_LABELS):
        r,c=index//2+1,index%2+1
        for prefix,name,color in [('', 'This segment',LOCAL),('peer_','LA peer',PEER)]:
            values=[row.get(f'{prefix}{metric}_median_{d}') for d,_ in periods]
            valid_n=[row.get(f'{prefix}{metric}_valid_n_{d}') for d,_ in periods]
            fig.add_trace(go.Bar(x=[label for _,label in periods],y=values,name=name,legendgroup=name,showlegend=index==0,marker_color=color,text=[f'{v:,.2f}' if pd.notna(v) else '' for v in values],textposition='outside',cliponaxis=False,customdata=valid_n,hovertemplate=f'%{{x}}<br>Median %{{y:,.2f}} {unit.lower()}<br>Valid observations: %{{customdata:,.0f}}<extra>{name}</extra>'),row=r,col=c)
        fig.update_yaxes(title_text=unit,rangemode='tozero',row=r,col=c)
        if metric=='value_score':fig.update_yaxes(range=[0,5.55],row=r,col=c)
    base(fig,550);fig.update_layout(barmode='group',legend=dict(orientation='h',x=0,y=1.17),margin=dict(l=40,r=25,t=75,b=30))
    for annotation in fig.layout.annotations:annotation.font.size=13
    return fig

def evidence_coverage(row, period=None, threshold=.8):
    periods=[(period,dict(PERIODS)[period])] if period else PERIODS
    labels=[];priced=[];missing=[];custom=[]
    for d,date in periods:
        for prefix,name in [('', 'Local'),('peer_', 'Peer')]:
            total=row.get(f'{prefix}listing_rows_{d}');valid=row.get(f'{prefix}priced_rows_{d}');share=row.get(f'{prefix}price_coverage_{d}')
            if pd.isna(total) or total<=0 or pd.isna(valid) or pd.isna(share):continue
            labels.append(f'{date} · {name}');priced.append(100*share);missing.append(100*(1-share));custom.append([valid,total,total-valid])
    if not labels:return empty('No listing population for coverage analysis.')
    fig=go.Figure()
    fig.add_trace(go.Bar(y=labels,x=priced,orientation='h',name='Valid price',marker_color=LOCAL,text=[f'{x:.1f}%' for x in priced],textposition='inside',customdata=custom,hovertemplate='%{y}<br>Coverage %{x:.1f}%<br>%{customdata[0]:,.0f} priced / %{customdata[1]:,.0f} listings<extra></extra>'))
    fig.add_trace(go.Bar(y=labels,x=missing,orientation='h',name='Price unavailable',marker_color=GRAY,customdata=custom,hovertemplate='%{y}<br>%{customdata[2]:,.0f} listings without a valid price<extra></extra>'))
    fig.add_vline(x=100*threshold,line_color=AMBER,line_dash='dash',annotation_text=f'Warning below {threshold:.0%}',annotation_position='bottom')
    base(fig,300 if period else 360);fig.update_layout(barmode='stack',xaxis=dict(range=[0,100],ticksuffix='%',title='Share of comparable listings'),yaxis=dict(autorange='reversed',showgrid=False))
    return fig

def bedroom_completeness(row):
    fig=go.Figure()
    for prefix,name,color in [('local','Local',LOCAL),('peer','LA peer',PEER)]:
        vals=[row.get(f'{prefix}_unknown_bedroom_share_{d}') for d,_ in PERIODS]
        bases=[row.get(f'{prefix}_bedroom_base_rows_{d}') for d,_ in PERIODS]
        fig.add_trace(go.Bar(x=['March','June'],y=[100*v if pd.notna(v) else None for v in vals],name=name,marker_color=color,text=[f'{v:.1%}' if pd.notna(v) else '' for v in vals],textposition='outside',cliponaxis=False,customdata=bases,hovertemplate='%{x}<br>Unknown bedrooms: %{y:.1f}%<br>Pre-bedroom population: %{customdata:,.0f}<extra>%{fullData.name}</extra>'))
    fig.add_hline(y=25,line_dash='dash',line_color=AMBER,annotation_text='25% caution',annotation_position='top left')
    base(fig,360);fig.update_layout(barmode='group',yaxis=dict(range=[0,110],ticksuffix='%',title='Listings excluded for unknown bedrooms'))
    return fig

def segment_label(frame):
    rooms=frame.room_type.replace({'Entire home/apt':'Entire home','Private room':'Private room','Shared room':'Shared room','Hotel room':'Hotel'})
    beds=frame.bedroom_segment.replace({'1 bedroom':'1 BR','2 bedroom':'2 BR','3 bedroom':'3 BR','4 bedroom':'4 BR','5 bedroom':'5 BR','6+ bedrooms':'6+ BR'})
    return frame.neighbourhood+' · '+rooms+' · '+beds

def priority_bars(ranked, limit=10):
    if ranked.empty:return empty()
    top=ranked.head(limit).copy();labels=segment_label(top)
    fig=go.Figure()
    for d,name,color in [('march','March',PEER),('june','June',LOCAL)]:
        fig.add_trace(go.Bar(y=labels,x=top[f'premium_pct_{d}'],orientation='h',name=name,marker_color=color,customdata=top[['rank','review_score',f'priced_rows_{d}',f'listing_rows_{d}']].values,hovertemplate='%{y}<br>%{fullData.name}: %{x:+.1f}%<br>Review priority %{customdata[0]:.0f} · score %{customdata[1]:.1f} pp<br>%{customdata[2]:,.0f} priced / %{customdata[3]:,.0f} listings<extra></extra>'))
    fig.add_vline(x=0,line_width=1,line_color='#72869a')
    base(fig,max(390,len(top)*52+80));fig.update_layout(barmode='group',xaxis=dict(title='Relative to same-date LA peer (%)',ticksuffix='%'),yaxis=dict(autorange='reversed',showgrid=False),legend=dict(orientation='h',y=1.07))
    return fig

def persistence_map(compared, direction='Both'):
    qualified=compared.dropna(subset=['premium_pct_march','premium_pct_june']).copy()
    if direction in ['Premium','Discount']:
        qualified=qualified.loc[qualified.direction.eq(direction)]
    if qualified.empty:return empty('No segments have qualifying premiums in both dates.')
    fig=go.Figure()
    for status,color in COLORS.items():
        data=qualified.loc[qualified.persistence_status.eq(status)]
        if data.empty:continue
        labels=segment_label(data)
        fig.add_trace(go.Scatter(x=data.premium_pct_march,y=data.premium_pct_june,mode='markers',name=status.replace('Persistent ','Persistent '),marker=dict(size=9,color=color,opacity=.7,line=dict(width=.5,color='white')),customdata=np.column_stack([labels,data.priced_rows_march,data.priced_rows_june]),hovertemplate='%{customdata[0]}<br>March %{x:+.1f}% · June %{y:+.1f}%<br>Priced listings: March %{customdata[1]}, June %{customdata[2]}<extra>%{fullData.name}</extra>'))
    fig.add_hline(y=0,line_color='#7c8b99');fig.add_vline(x=0,line_color='#7c8b99')
    base(fig,440);fig.update_layout(xaxis=dict(title='March premium / discount (%)',ticksuffix='%'),yaxis=dict(title='June premium / discount (%)',ticksuffix='%'),legend=dict(orientation='h',y=1.18))
    return fig

def pattern_counts(compared):
    order=list(COLORS)
    counts=compared.persistence_status.value_counts().reindex(order,fill_value=0)
    if compared.empty:return empty()
    labels=['Persistent premium','Persistent discount','Reversed direction','Neutral','Insufficient evidence']
    fig=go.Figure(go.Bar(y=labels,x=counts.values,orientation='h',marker_color=list(COLORS.values()),text=counts.values,textposition='outside',cliponaxis=False,hovertemplate='%{y}: %{x:,} segments<extra></extra>'))
    base(fig,330);fig.update_layout(yaxis=dict(autorange='reversed',showgrid=False),xaxis_title='Number of segments · all shared filters',showlegend=False)
    return fig
