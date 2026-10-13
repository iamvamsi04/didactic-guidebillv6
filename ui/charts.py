"""Render a small fixed chart vocabulary; never execute model-supplied code or specs."""
import altair as alt
import streamlit as st


def render_chart(chart):
    x, ys = chart['x'], chart['y']
    rows = [{'x_value':r[x], 'value':r[y], 'series':y, 'position':i}
            for i,r in enumerate(chart['data']) for y in ys]
    base = alt.Chart(alt.Data(values=rows))
    measure_title = chart.get('currency') or (ys[0] if len(ys)==1 else 'Value')
    kind = chart['type']
    tooltip = [alt.Tooltip('x_value:Q' if kind=='scatter' else 'x_value:N',title=x),
               alt.Tooltip('series:N',title='Measure'),alt.Tooltip('value:Q',title=measure_title,format=',.2f')]
    if kind == 'pie':
        result = base.mark_arc(innerRadius=45).encode(theta='value:Q',color=alt.Color('x_value:N',title=x),tooltip=tooltip)
    elif kind == 'scatter':
        result = base.mark_circle(size=70).encode(x=alt.X('x_value:Q',title=x),
                y=alt.Y('value:Q',title=measure_title),tooltip=tooltip)
    else:
        result = {'bar':base.mark_bar,'line':base.mark_line,'area':base.mark_area}[kind]()
        result = result.encode(x=alt.X('x_value:O',title=x,sort=alt.SortField(field='position',order='ascending')),
            y=alt.Y('value:Q',title=measure_title,stack=None),color=alt.Color('series:N',title='Measure'),tooltip=tooltip)
        if kind == 'bar' and len(ys)>1:
            result = result.encode(xOffset='series:N')
    st.subheader(chart['title'])
    st.altair_chart(result.properties(height=320),use_container_width=True)
    st.caption('Based on the saved query result' + (f" · {chart['currency']}" if chart.get('currency') else '') + '. Refresh the question for current figures.')
    with st.expander('View chart data'):
        st.dataframe(chart['data'],hide_index=True,use_container_width=True)
