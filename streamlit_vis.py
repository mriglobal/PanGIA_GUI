import matplotlib.pyplot as plt
import numpy as np
import os
from pathlib import Path
from math import pi
from operator import itemgetter
import re
import streamlit as st
import pandas as pd
from bokeh.transform import linear_cmap, dodge
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, Div, FactorRange, Range1d, TapTool, ColorBar, CDSView
from bokeh.palettes import Spectral11, Turbo256
import textwrap
import warnings


warnings.filterwarnings("ignore", category=DeprecationWarning)
st.set_page_config(layout="wide")

###
##### Upload method for stand-alone, CLI-based runs:
###

# upload_tsv = st.file_uploader("PanGIA output to visualize:", type=['.tsv', '.csv'], accept_multiple_files=False, key=None,
#             help="Select a .tsv/.csv file to generate a dynamic graph!", on_change=None, args=None,
#             kwargs=None, disabled=False)

# if upload_tsv is not None:

#    df = df.sort_values(by="Score", ascending=False)
#    df = df.drop_duplicates(subset=["Taxa"], keep='first')
#    df["PATHOGEN"].fillna(value='Non-Pathogen', inplace=True)

###
##### Initialize params to be filled by widgets:
###

# File params:
tsv_file = ''
log_file = ''
scaledown_files = []
df = pd.DataFrame()
params = st.experimental_get_query_params()
#params = st.query_params
pangia_filepath = params['tsv'][0]
pangia_output = []
pievalue_list = []
info = {}

# Checkbox/Checklist params:
phylum_check = ''
genus_check = ''
species_check = ''
strain_check = ''
sd_strain = ''
pathogen_check = ''
non_pathogen_check = ''
sd_taxid = 0



###
##### Pull in all results files for the current PanGIA run:
###

for file in os.listdir(pangia_filepath):
    if os.path.isfile(os.path.join(pangia_filepath, file)):
        pangia_output.append(file)


# Separate/Isolate files for downstream use:
for file in pangia_output:
    if file.endswith('.tsv'):
        tsv_file = file
    if file.endswith('.log'):
        log_file = file
    if file.endswith('.scaledown'):
        scaledown_files.append(file)

###
##### Read in TSV file as a dataframe:
###

if tsv_file is not None:

    df = pd.read_csv(pangia_filepath + '/' + tsv_file, sep='\t')
    df = df.sort_values(by="SCORE", ascending=False)
    df = df.drop_duplicates(subset=["NAME"], keep='first')
    df = df.drop_duplicates(subset=["TAXID"], keep='first')
    df["PATHOGEN"].fillna(value='Non-Pathogen', inplace=True)
    df = df.round({'TAXID': 2})

    # Now, change all keys to be a bit more reasonable sounding/looking:
    df.rename(columns={'LEVEL': 'Level', 'NAME': 'Taxa', 'TAXID': 'TAXID', 'READ_COUNT': 'READ_COUNT',
                       'READ_COUNT_RNR': 'READ_COUNT_RNR', 'LINEAR_COV': 'LINEAR_COV',
                       'DEPTH_COV': 'DEPTH_COV', 'DEPTH_COV_NR': 'DEPTH_COV_NR',
                       'RS_DEPTH_COV_NR': 'RS_DEPTH_COV_NR', 'PATHOGEN': 'Pathogenicity',
                       'SCORE': 'Score', 'REL_ABUNDANCE': 'REL_ABUNDANCE', 'ABUNDANCE': 'Abundance',
                       'TOTAL_BP_MISMATCH': 'TOTAL_BP_MISMATCH', 'NOTE': 'NOTE', 'RPKM': 'RPKM',
                       'PRI_READ_COUNT': 'PRI_READ_COUNT', 'TOL_RS_READ_CNT': 'TOL_RS_READ_CNT',
                       'TOL_RS_RNR': 'TOL_RS_RNR', 'TOL_GENOME_SIZE': 'TOL_GENOME_SIZE',
                       'LINEAR_LENGTH': 'LINEAR_LENGTH', 'TOTAL_BP_MAPPED': 'TOTAL_BP_MAPPED',
                       'RS_DEPTH_COV': 'RS_DEPTH_COV', 'TOL_NS_READ_CNT': 'TOL_NS_READ_CNT',
                       'TOL_NS_RNR': 'TOL_NS_RNR', 'FLAG': 'Flag',
                       'READ_COUNT_RSNB': 'READ_COUNT_RSNB',

                       'STR': 'Strain Read Count', 'SPE': 'Species Read Count', 'GEN': 'Genus Read Count', 'FAM': 'Family Read Count',
                       'ORD': 'Order Read Count', 'CLA': 'Clade Read Count', 'PHY': 'Phylum Read Count', 'SK': 'Superkingdom Read Count',
                       'ROOT': 'Root Read Count',

                       'STR_rnb': 'Strain Reference/Identity-Normalized Rank-Specific Read Count',
                       'SPE_rnb': 'Species Reference/Identity-Normalized Rank-Specific Read Count',
                       'GEN_rnb': 'Genus Reference/Identity-Normalized Rank-Specific Read Count',
                       'FAM_rnb': 'Family Reference/Identity-Normalized Rank-Specific Read Count',
                       'ORD_rnb': 'Order Reference/Identity-Normalized Rank-Specific Read Count',
                       'CLA_rnb': 'Clade Reference/Identity-Normalized Rank-Specific Read Count',
                       'PHY_rnb': 'Phylum Reference/Identity-Normalized Rank-Specific Read Count',
                       'SK_rnb': 'Superkingdom Reference/Identity-Normalized Rank-Specific Read Count',
                       'ROOT_rnb': 'Root Reference/Identity-Normalized Rank-Specific Read Count',

                       'STR_rnr': 'Strain Reference-Normalized Read Count',
                       'SPE_rnr': 'Species Reference-Normalized Read Count',
                       'GEN_rnr': 'Genus Reference-Normalized Read Count',
                       'FAM_rnr': 'Family Reference-Normalized Read Count',
                       'ORD_rnr': 'Order Reference-Normalized Read Count',
                       'CLA_rnr': 'Clade Reference-Normalized Read Count',
                       'PHY_rnr': 'Phylum Reference-Normalized Read Count',
                       'SK_rnr': 'Superkingdom Reference-Normalized Read Count',
                       'ROOT_rnr': 'Root Reference-Normalized Read Count',

                       'STR_ri': 'Strain Read-Mapping Identity Read Count',
                       'SPE_ri': 'Species Read-Mapping Identity Read Count',
                       'GEN_ri': 'Genus Read-Mapping Identity Read Count',
                       'FAM_ri': 'Family Read-Mapping Identity Read Count',
                       'ORD_ri': 'Order Read-Mapping Identity Read Count',
                       'CLA_ri': 'Clade Read-Mapping Identity Read Count',
                       'PHY_ri': 'Phylum Read-Mapping Identity Read Count',
                       'SK_ri': 'Superkingdom Read-Mapping Identity Read Count',
                       'ROOT_ri': 'Root Read-Mapping Identity Read Count', 'HOST': 'Host Organism',
                       'DISEASE':'Diseases Caused', 'SCORE_UNIQ': 'Overall Uniqueness Score',
                       'SCORE_BG': 'SCORE_BG', 'SCORE_UNIQ_CUR_LVL': 'SCORE_UNIQ_CUR_LVL'
                       }, inplace=True)


#("Name", "@Name"),
#("Tax-ID", "@Tax-ID"),
#("Score", "@Score{0.00}"),
#("Linear Coverage", "@Linear Coverage{0,0.00}"),
#("Depth-of-Coverage", "@Depth-of-Coverage{0,0.00}"),
#("Normalized Rank-Specific Depth-of-Coverage (RSNR)", "@Normalized Rank-Specific Depth-of-Coverage{0,0.00}"),
#("Relative Abundance", "@Relative Abundance{0,0.00}"),
#("Raw Read Count", "@Raw Read Count{0,0}"),
#("Reference-Normalized Read Count", "@Reference-Normalized Read Count{0,0.00}"),
#("Normalized Rank-Specific Read Count)", "@Normalized Rank-Specific Read Count{0,0.00}"),
#("Primary Read", "@Primary Read{0,0}"),
#("RPKM", "@RPKM{0,0.00}"),
#("Score (Unique)", "@Score (Unique){0.00}"),
#("Score (Background)", "@Score (Background){0.00}"),
#("Genome Size (bp)", "@Genome Size (bp){0,0}"),
#("Pathogenicity", "@Pathogenicity"),

else:
    print("No dataframe.")


###
##### Supporting Methods:
###

# Called by the big pie-chart method to pull in the correct values to return to it's ColumnDataSource:
def genPieValues(infodict):
    tol_cnt = 0
    ang_start = 0
    ang_size = 6.27
    colors = list(itemgetter(9, 3, 0, 1, 2, 5, 7, 8, 9)(Spectral11))

    p_name, p_str_ang, p_stp_ang, p_col, p_val, p_pct = [], [], [], [], [], []
    test_patho_values = []

    # Account for each dictionary type:
    keys = infodict.keys()

    if "Pathogen" in keys:
        for values in infodict.values():
            p_val.append(values)
        tol_cnt = sum(infodict.values())

    else:
        for values in infodict.values():
            p_val.append(values)
            for num in p_val:
                tol_cnt += num

    percents = [0]
    for name in infodict:
        pct = infodict[name] / tol_cnt
        p_pct.append(pct)
        p_name.append("%.1f%% %s" % (pct * 100, name))
        percents.append(percents[-1] + (infodict[name] / tol_cnt))

    p_str_ang = [p * 2 * pi for p in percents[:-1]]
    p_stp_ang = [p * 2 * pi for p in percents[1:]]
    p_col = colors[:len(p_name)]

    pievalue_list = [p_name, p_str_ang, p_stp_ang, p_col, p_val, p_pct]

    return pievalue_list


# Becaue the in-reads piechart is constructed base on information stored in the logfile
# (instead of the .tsv), we use this method to get counts of the reads from 'target', 'host', and 'ignored'.
def parseLog(path):
    total_input = 0
    total_mapped = 0
    info = {}
    info['Target'] = 0
    info['Host'] = 0
    info['Ignored'] = 0

    for file in os.scandir(path):
        if '.pangia.log' in Path(file).name:
            with open(file, 'r') as f:
                for line in f:
                    if "Total number of input reads" in line:
                        reg = re.search('Total number of input reads: (\d+)', line)
                        total_input = int(reg.group(1))
                    elif "Total number of mapped reads" in line:
                        reg = re.search('Total number of mapped reads: (\d+)', line)
                        total_mapped = int(reg.group(1))
                    elif "Total number of host reads" in line:
                        reg = re.search('Total number of host reads: (\d+)', line)
                        info['Host'] = int(reg.group(1))
                    elif "Done processing SAM file" in line:
                        reg = re.search('Done processing SAM file, (\d+) alignment', line)
                        total_mapped = int(reg.group(1))
                    elif "Database          : [" in line:
                        reg = re.search('Database          : \[(.+)\]', line)
                        db_string = reg.group(1)
                        db_string = db_string.strip("'")
                        global db_path
                        db_file = db_string.split("', '")[0]
                        db_path = "/".join(db_file.split("/")[:-1])
                    elif "Total number of ignored reads" in line:
                        reg = re.search('Total number of ignored reads .*: (\d+)', line)
                        info['Ignored'] = int(reg.group(1))
                        break

                info['Target'] = total_mapped - info['Host'] - info['Ignored']

                if total_input > 0:
                    info['Unmapped'] = total_input - total_mapped

                return info

# Define what the text-pop ups will say when hovering over a given value.
# Note the one-to-one correspondance to variable names in source.data (from self.source).
# These tools are instantiated by adding a 'tools=[]' argument to figure construction.
def define_tooltips():
    hoverlist = []
    hover_graph = HoverTool(tooltips=[
        ("Name", "@Taxa"),
        ("Tax-ID", "@TAXID{0}"),
        ("Score", "@Score{0.00}"),
        #("Linear Coverage", "@LINEAR_COV"),
        #("Depth-of-Coverage", "@DEPTH_COV"),
        #("Normalized Rank-Specific Depth-of-Coverage (RSNR)", "@RS_DEPTH_COV_NR"),
        ("Relative Abundance", "@REL_ABUNDANCE{0.00}"),
        ("Raw Read Count", "@READ_COUNT{0,0}"),
        ("Reference-Normalized Read Count", "@READ_COUNT_RNR"),
        #("Normalized Rank-Specific Read Count)", "@READ_COUNT_RSNB"),
        #("Score (Unique)", "@SCORE_UNIQ"),
        #("Score (Background)", "@SCORE_BG"),
        ("Pathogenicity", "@Pathogenicity"),
    ],
        mode='vline'
    )

    pie_hover = HoverTool(tooltips=[("Name", "@name"),
                                    ("Reads", '@val{,} (@pct{%0.0f})')
                                    ])

    hoverlist = [hover_graph, pie_hover]
    return hoverlist

hoverlist = define_tooltips()

###
###### Streamlit!
###

#st.title('PanGIA Report')

with st.sidebar:

    #with st.expander("Choose which columns to exclude from the view!"):
    #
    #    'Default Included Columns:'
    #
    #    'Default Excluded Columns:'
    #
    #    with st.container():
    #
    #        num_removal, text_removal = st.columns(2)
    #
    #        with num_removal:
    #
    #            select_rpkm = st.checkbox('Reads Per Kilobase Million', value=False)
    #            select_rsnb = st.checkbox('Reference/Identity-Normalized Rank-Specific Read Count', value=False)
    #            select_lin_cov = st.checkbox('Linear Coverage', value=False)
    #            select_depth_cov = st.checkbox('Depth of Coverage', value=False)
    #            select_rs_dep_cov_nr = st.checkbox('Reference-Normalized Rank-Specific Depth of Coverage', value=False)
    #            select_dep_cov_nr = st.checkbox('Reference-Normalized Depth of Coverage', value=False)
    #
    #        with text_removal:
    #
    #            select_note = st.checkbox('Additional Notes', value=False)

    #with st.expander("See options for filtering by specific taxa here!"):
    #    spe_substring = st.checkbox("Taxa Substring for Inclusion:", value=False)
    #    rej_spe_substring = st.checkbox("Taxa Substring for Exclusion:", value=False)
    #
    #    if spe_substring:
    #        substring = st.text_input("Taxa Substring for Inclusion:")
    #        substring = substring.replace(' or ', '|')
    #    else:
    #        substring = ''
    #
    #    if rej_spe_substring:
    #        rej_substring = st.text_input("Taxa Substring for Exclusion:")
    #        rej_substring = rej_substring.replace(' or ', '|')
    #    else:
    #        rej_substring = ''
    #
    #    if st.button("search"):
    #        if substring != '':
    #            df = df[df['Taxa'].str.contains(substring, case=False, na=False)]
    #
    #    if rej_substring != '':
    #        df = df[~df['Taxa'].str.contains(rej_substring, case=False, na=False)]

    #with st.expander("See options for adjusting what is plotted on the X and Y axes here! " + '\n' +
    #                 " You can also adjust which variables represent glyph size and color! "):

    #    'Axes Adjustment:'
    #    selected_x_var = st.selectbox('What will be graphed on the X-axis?', ['Taxa', 'Tax-ID'], index=0)
    #    selected_y_var = st.selectbox('What will be graphed on the Y-axis?', ['Relative Abundance', 'Reference-Normalized Read Count'], index=1)

    #    'Glyph Adjustment:'
    #    selected_color_var = st.selectbox('What will be used as a color?',
    #                                      ['Score', 'Reference-Normalized Read Count'], index=0, help="Adjustment of which normalized variable represents glyph color.")
    #    size_param = st.selectbox('Which variable should control glyph size?',
    #                              ['Score', 'Relative Abundance'], index=0, help="Adjustment of which normalized variable represents glyph size.")

    selected_x_var = 'Taxa'
    selected_y_var = 'READ_COUNT_RNR'
    selected_color_var = 'Score'
    size_param = 'Score'

    'Select Taxonomic Rank:'
    select_rank_phylum = st.checkbox('phylum', value=True, help="Toggle to add or remove phylum-level data.")
    select_rank_genus = st.checkbox('genus', value=True, help="Toggle to add or remove genus-level data.")
    select_rank_species = st.checkbox('species', value=True, help="Toggle to add or remove species-level data.")
    select_rank_strain = st.checkbox('strain', value=True, help="Toggle to add or remove strain-level data.")

    st.markdown("""---""")
    'Select for Pathogenicty:'
    select_pathogen = st.checkbox('Pathogen', value=True, help="Toggle to add or remove pathogenic taxa.")
    select_non_pathogen = st.checkbox('Non-Pathogen', value=True, help="Toggle to add or remove non-pathogenic taxa data.")

    st.markdown("""---""")
    slider_min_score = st.slider("Filter by score:", 0.0, 1.0, value=((min(df["Score"]), max(df["Score"]))))
    slider_norm_rd_cnt = st.slider("Filter by normalized read count:", float(1), float(max(df["READ_COUNT_RNR"])),
        value=((max(df["READ_COUNT_RNR"])*0.02, max((df["READ_COUNT_RNR"])))))

    if select_rank_phylum:
        phylum_check = 'phylum'
    if select_rank_genus:
        genus_check = 'genus'
    if select_rank_species:
        species_check = 'species'
    if select_rank_strain:
        species_check = 'strain'

    if select_pathogen:
        pathogen_check = 'Pathogen'
    if select_non_pathogen:
        non_pathogen_check = 'Non-Pathogen'

    #if select_rpkm == False:
    df = df.drop(columns=['RPKM'])
    #if select_note == False:
    df = df.drop(columns=['NOTE'])
    #if select_rsnb == False:
    df = df.drop(columns=['READ_COUNT_RSNB'])
    #if select_lin_cov == False:
    df = df.drop(columns=['LINEAR_COV'])
    #if select_depth_cov == False:
    df = df.drop(columns=['DEPTH_COV'])
    #if select_dep_cov_nr == False:
    df = df.drop(columns=['DEPTH_COV_NR'])
    #if select_rs_dep_cov_nr == False:
    df = df.drop(columns=['RS_DEPTH_COV_NR'])

    # checkbox filters:
    df = df[df['Level'].isin([phylum_check, genus_check, species_check])]
    df = df[df['Pathogenicity'].isin([pathogen_check, non_pathogen_check])]

    # slider filters:
    df = df[df['Score'] >= slider_min_score[0]]
    df = df[df['Score'] <= slider_min_score[1]]

    df = df[df['READ_COUNT_RNR'] >= slider_norm_rd_cnt[0]]
    df = df[df['READ_COUNT_RNR'] <= slider_norm_rd_cnt[1]]

    st.markdown("""---""")
    select_scaledown = st.selectbox('Select a strain in the current view:', df.loc[df['Level'] == 'strain', 'Taxa'], index=0)

    try:
        sd_strain = df.loc[df['Taxa'] == select_scaledown, 'TAXID'].iloc[0]
        print(sd_strain)
        if str(sd_strain).split('.')[-1] == '0':
            sd_strain = str(sd_strain).split('.')[0]
    except IndexError:
        sd_strain = 'None'
        strain_name = 'None'
    except FileNotFoundError:
        sd_strain = 'None'

# Filtered and sortable (by clicking on columns) dataframe:
print('Click on any column to filter the dataframe!')
df = df.sort_values(by=["Level", "Taxa", "Score", "READ_COUNT_RNR"], ascending=True)

    ###
    ##### BSAT Information is not currently included in depth-scaledown plots!
    ###

    #    bsat_fn = f"{self.filepath}/{acc}.bsat.bed"
    #    if not os.path.isfile(bsat_fn):
    #        bsat_fn = f"{db_path}/BSAT_markers/{acc}.bsat.bed"
    #        pass

    #    if os.path.isfile(bsat_fn) and os.path.getsize(bsat_fn) > 0:
    #        coverage_p_log.title.text = f"Loading BSAT coordinates for {gc_ref}..."
    #        coverage_p_lin.title.text = f"Loading BSAT coordinates for {gc_ref}..."
    #        # loading coverage files
    #        bsat_df = pd.read_csv(bsat_fn, sep='\t', header=None, names=['ref', 'str', 'end', 'note'])
    #        # pu = pu.drop_duplicates(subset=['ref', 'str', 'end'])
    #        bsat['b_ref'] += [gc_ref for x in bsat_df['note'].tolist()]
    #        bsat['b_str'] += (bsat_df['str'] + offset).tolist()
    #        bsat['b_end'] += (bsat_df['end'] + offset).tolist()
    #        bsat['b_col'] += [note_color[x] for x in bsat_df['note'].tolist()]
    #        bsat['b_not'] += bsat_df['note'].tolist()

    #    bsat_source.data = bsat

    # BSAT scaledown plots (not currently used - no BSAT source in scaledown).
    # coverage_p_log.hbar(left='b_str', right='b_end', y=0.3, height=0.13, source=bsat_source,
    #                    name="b_bsat", y_range_name="BSAT")
    # coverage_p_lin.hbar(left='b_str', right='b_end', y=2.3, height=1.0, source=bsat_source,
    #                    name="b_bsat", y_range_name="BSAT")


###
###### Construct Piecharts from PanGIA logfile and .tsv output:
###

# Initialize piechart data sources:
pieInReadsDS = ColumnDataSource(
    data=dict(name=['NA'], start_angle=[0], end_angle=[2 * pi], color=['#EFF0F1'], val=['NA'], pct=['NA']))
pieFlagDS = ColumnDataSource(
    data=dict(name=['NA'], start_angle=[0], end_angle=[2 * pi], color=['#EFF0F1'], val=['NA'], pct=['NA']))
piePathoDS = ColumnDataSource(
    data=dict(name=['NA'], start_angle=[0], end_angle=[2 * pi], color=['#EFF0F1'], val=['NA'], pct=['NA']))

# "In-Reads" chart - information comes from PanGIA logfile:
info_dict = parseLog(str(pangia_filepath))
info_dict = dict(info_dict)
info_dict_type = type(info_dict)

pievalue_list = genPieValues(info_dict)

pieInReadsDS.data = dict(
    name=pievalue_list[0], start_angle=pievalue_list[1], end_angle=pievalue_list[2],
    color=pievalue_list[3], val=pievalue_list[4], pct=pievalue_list[5])


# "Pathos" chart - information comes from PanGIA .tsv:
info = {}
info['Pathogen'] = df.loc[df.Pathogenicity == "Pathogen", "PRI_READ_COUNT"].sum()
info['Not pathogen'] = df.loc[:, "PRI_READ_COUNT"].sum() - info['Pathogen']

pievalue_list = genPieValues(info)

piePathoDS.data = dict(
    name=pievalue_list[0], start_angle=pievalue_list[1], end_angle=pievalue_list[2],
    color=pievalue_list[3], val=pievalue_list[4], pct=pievalue_list[5])

# "Flag" chart - information comes from PanGIA .tsv:

if "Flag" in df:
    info = {}
    for flag in df.Flag.unique():
        if flag == 'B':
            name = "Bacteria"
        elif flag == 'A':
            name = "Archae"
        elif flag == 'E':
            name = "Eukaryota"
        elif flag == 'V':
            name = "Viruses"
        else:
            name = flag

        info[name] = df.loc[df.Flag == flag, "PRI_READ_COUNT"].sum()

    pievalue_list = genPieValues(info)
    pieFlagDS.data = dict(
        name=pievalue_list[0], start_angle=pievalue_list[1], end_angle=pievalue_list[2],
        color=pievalue_list[3], val=pievalue_list[4], pct=pievalue_list[5])

######
###### BUILD OUT PIECHARTS:
######

hover_in_reads = define_tooltips()
hover_flag = define_tooltips()
hover_patho = define_tooltips()

###### Log File In-Reads Pie Chart:
pieInReadsFigure = figure(
    plot_width=350,
    plot_height=200,
    x_range=(-1.3, 4),
    y_range=(-2, 2),
    title="Total reads:",
    tools=[hover_in_reads[1]]
)

pieInReadsFigure.annular_wedge(
    x=0, y=0, alpha=0.7,
    legend_field='name', start_angle='start_angle', end_angle='end_angle', color='color',
    inner_radius=0.7, outer_radius=1.2, source=pieInReadsDS
)

###### Flag Distribution Piechart:
pieFlagFigure = figure(
    plot_width=350,
    plot_height=200,
    x_range=(-1.5, 4),
    y_range=(-2, 2),
    title="Target reads distribution:",
    tools=[hover_flag[1]]
)

pieFlagFigure.annular_wedge(
    x=0, y=0, alpha=0.7,
    legend_field='name', start_angle='start_angle', end_angle='end_angle', color='color',
    inner_radius=0.7, outer_radius=1.2, source=pieFlagDS
)

###### Pathogen Stats Piechart:
piePathoFigure = figure(
    plot_width=350,
    plot_height=200,
    x_range=(-1.27, 4),
    y_range=(-2, 2),
    title="Pathogen reads distribution:",
    tools=[hover_patho[1]]
)

piePathoFigure.annular_wedge(
    x=0, y=0, alpha=0.7,
    legend_field='name', start_angle='start_angle', end_angle='end_angle', color='color',
    inner_radius=0.7, outer_radius=1.2, source=piePathoDS
)

# Output piecharts:
piechart_list = [pieInReadsFigure, pieFlagFigure, piePathoFigure]

for chart in piechart_list:
    chart.axis.visible = False
    chart.grid.visible = False
    chart.legend.location = "center_right"
    chart.toolbar.logo = None
    chart.toolbar_location = None
    chart.outline_line_width = 0
    chart.outline_line_alpha = 0

col1, col2, col3 = st.columns(3)

col1.bokeh_chart(pieInReadsFigure)
col2.bokeh_chart(pieFlagFigure)
col3.bokeh_chart(piePathoFigure)

#scaledown_files

@st.cache_data
def convert_df(df):
# IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv().encode('utf-8')

csv = convert_df(df)
st.download_button(label = "Download filtered view as a CSV", data = csv, file_name="test_name.csv", mime='text/csv')

source = ColumnDataSource()
df = df.drop_duplicates(subset=["TAXID"], keep='first')
dict_df = df.to_dict(orient='list')
source.data = dict_df

source.data[selected_x_var] = [str(i) for i in source.data[selected_x_var]]

x_range = FactorRange(*source.data[selected_x_var])
x_range
color_label = selected_color_var + " ---  Normalized Between 0 and 1"

dotplot = figure(
                 x_range=x_range, y_range=(0, max(source.data[selected_y_var])),
                 tools=["wheel_zoom, box_zoom, reset, tap", hoverlist[0]],
                 sizing_mode="stretch_width"
                 )

# We use customizable parameters for color, size, and y-axis - see source.data!
color_map = linear_cmap(field_name=selected_color_var, palette=Turbo256, low=min(source.data[selected_color_var]),
                        high=max(source.data[selected_color_var]))
color_bar = ColorBar(color_mapper=color_map['transform'], width=20, label_standoff=12, title=color_label,
                     title_text_align='left', title_text_font_size='12px')
dotplot.add_layout(color_bar, 'right')

dotplot.xaxis.axis_label = selected_x_var
dotplot.xaxis.major_label_orientation = 3.1415926 / 4
dotplot.yaxis.axis_label = selected_y_var
dotplot.background_fill_color = "white"
dotplot.background_fill_alpha = 0.5
dotplot.outline_line_width = 6
dotplot.outline_line_alpha = 0.1
dotplot.outline_line_color = "navy"
dotplot.x_range.range_padding = 0

dotplot.circle(x=dodge(selected_x_var, 0.0, range=dotplot.x_range), y=selected_y_var, source=source, radius=size_param,
               color=color_map, fill_alpha=0.6, line_alpha=0.7)

st.bokeh_chart(dotplot)

pd.set_option('display.max_colwidth', 20)
st.write(df)

###
##### Scaledown plot based on strain-selectbox:
###

if select_scaledown == None:

    graph_title = 'Not available at this rank (strain only)'

else:

    sd_taxid = df.loc[df['Taxa'] == select_scaledown, 'TAXID'].iloc[0]

    if str(sd_taxid).split('.')[-1] == '0':
        sd_taxid = str(sd_strain).split('.')[0]

    graph_title = "Strain: " + select_scaledown + " | Taxid: " + str(sd_taxid)

    # Create hovertools for scaledown plots - consider bringing these down to the hover method
    hover_gcov_lin = HoverTool(tooltips=[
        ("Depth", "information"),
        ("Reference", "@gc_ref"),
        ("Position", "@gc_pos"),
        ("Depth", "@gc_dep")],
        names=['b_gcov'],
        mode='vline'
    )
    hover_gcov_log = HoverTool(tooltips=[
        ("Depth", "information"),
        ("Reference", "@gc_ref"),
        ("Position", "@gc_pos"),
        ("Depth", "@gc_dep")],
        names=['b_gcov'],
        mode='vline'
    )
    hover_bsat_lin = HoverTool(tooltips=[
        ("Marker", "information"),
        ("Reference", "@b_ref"),
        ("Location", "@b_str..@b_end"),
        ("Note", "@b_not")],
        names=['b_bsat'],
        mode='vline'
    )


    hover_bsat_log = HoverTool(tooltips=[
        ("Marker", "information"),
        ("Reference", "@b_ref"),
        ("Location", "@b_str..@b_end"),
        ("Note", "@b_not")],
        names=['b_bsat'],
        mode='vline'
    )

    # Create empty scaledown plots to be populated:
    coverage_p_lin = figure(
        plot_width=800,
        plot_height=200,
        min_border=0,
        title="Linear Scaledown Plot:",
        y_axis_label='Depth (x)',
        tools=["wheel_zoom,box_zoom,reset,save", hover_gcov_lin, hover_bsat_lin]
    )

    coverage_p_log = figure(
        plot_width=800,
        plot_height=200,
        min_border=0,
        title="Logrithmic (Base 10) Scaledown Plot:",
        y_axis_label='Depth (x)',
        y_axis_type="log",
        tools=["wheel_zoom,box_zoom,reset,save", hover_gcov_log, hover_bsat_log]
    )

    coverage_p_log.y_range.start = 0.1
    coverage_p_lin.y_range.start = 0
    coverage_p_log.x_range.start = 0
    coverage_p_lin.x_range.start = 0

    sd_file = pangia_filepath + "/" + str(sd_taxid) + ".depth.scaledown"

    # Read in scaledown results into a dataframe - then eliminate dupes for the coverage plot.
    sd_gcov_df = pd.read_csv(sd_file, sep='\t', header=None, names=['ref', 'pos', 'dep'])
    sd_gcov_df = sd_gcov_df.drop_duplicates(subset=['ref', 'pos'])
    sd_gcov_log_df = sd_gcov_df

    # Reference colors? I may need to bring in color bar or gradient here, as before.
    #coverage_color = {}

    coverage_names = sd_gcov_df['ref'].unique().tolist()

    # Add some color here based on all the unique values, and assign to dict. Then referencd later, I think?

    gcov_source = ColumnDataSource()
    gcov_source.data = dict(
        gc_ref = sd_gcov_df['ref'].to_list(),
        gc_pos = sd_gcov_df['pos'].to_list(),
        gc_dep = sd_gcov_df['dep'].to_list())

    gcov_log_source = ColumnDataSource()
    gcov_log_source.data = dict(
        gc_ref = sd_gcov_log_df['ref'].to_list(),
        gc_pos = sd_gcov_log_df['pos'].to_list(),
        gc_dep = sd_gcov_log_df['dep'].to_list())

    coverage_p_log.vbar(x='gc_pos', top='gc_dep', width=1, bottom=0.1, alpha=0.2, name="b_gcov",
                        source=gcov_log_source)

    coverage_p_lin.vbar(x='gc_pos', top='gc_dep', width=1, bottom=0, alpha=0.2, name="b_gcov",
                        source=gcov_source)

    max_gc_dep = max(gcov_log_source.data['gc_dep'])
    coverage_p_log.y_range.end = max_gc_dep*3
    coverage_p_lin.y_range.end = max_gc_dep*1.1

    note_color = {} # Might need some kind of color making here.
    offset = 1
    bsat = dict(b_ref=[], b_str=[], b_end=[], b_col=[], b_not=[])

    for gc_ref in sd_gcov_df['ref'].unique().tolist():
        (acc, leng, taxid, tag) = gc_ref.split('|')
        offset += int(leng)

    # Adjusting axes and data in scaledown COVERAGE plots:
    coverage_p_lin.x_range.start = min(gcov_source.data['gc_pos']) - 0.1*min(gcov_source.data['gc_pos'])
    coverage_p_log.x_range.start = min(gcov_source.data['gc_pos']) - 0.1*min(gcov_log_source.data['gc_pos'])
    coverage_p_lin.x_range.end = max(gcov_source.data['gc_pos']) + 0.1*max(gcov_source.data['gc_pos'])
    coverage_p_log.x_range.end = max(gcov_source.data['gc_pos']) + 0.1*max(gcov_log_source.data['gc_pos'])

    # Additional y-range for BSATs (not currently used):
    coverage_p_log.extra_y_ranges = {"BSAT": Range1d(start=0.1, end=10)}
    coverage_p_lin.extra_y_ranges = {"BSAT": Range1d(start=0, end=10)}

    graph_title

    st.bokeh_chart(coverage_p_lin)
    st.bokeh_chart(coverage_p_log)
