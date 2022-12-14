__name__ = "PanGIA-VIS: PanGIA result visualization tool: class-based Bokeh implementation"
__author__ = "August (Gus) Thomas"
__adaptedfrom__ = "PanGIA-VIS: PanGIA result visualization tool, By: Po-E (Paul) Li, Bioscience Division, Los Alamos National Laboratory"
__version__ = "0.9.2"
__date__ = "2022/2/02"

import pandas as pd
import numpy as np
import sys
import os
import json
from json import loads
from math import pi
from operator import itemgetter
import re
import hashlib
from os.path import dirname, join, isfile
from bokeh.io import curdoc
from bokeh.plotting import figure, output_file, show
from bokeh.layouts import row, layout, widgetbox, column
from bokeh.models import ColumnDataSource, HoverTool, Div, FactorRange, Range1d, TapTool, CustomJS, ColorBar, CDSView, \
    GroupFilter, MultiSelect, LinearAxis
from bokeh.models.widgets import Button, Slider, Select, TextInput, RadioButtonGroup, DataTable, TableColumn, \
    NumberFormatter, Panel, Tabs, HTMLTemplateFormatter, Toggle, CheckboxButtonGroup
from bokeh.models.callbacks import CustomJS
from bokeh.palettes import RdYlBu11, Spectral4, Spectral11, Set1, Viridis256, Turbo256
from bokeh.util import logconfig
from bokeh.resources import INLINE
from bokeh.embed import components, autoload_static
from bokeh.transform import factor_cmap, linear_cmap, dodge
from app.models import Results, ResultsToItem, Item
from pathlib import Path
import math
from sklearn import preprocessing
from functools import reduce

# ----------------------------------------------------------------------------------------------------------------------
# BOKEH CLASS
# ----------------------------------------------------------------------------------------------------------------------

# Look into adding optional argument to classes: replace old dataframe with new df.
class BokehObject():
    ###############################################################################
    # init global variables --- not sure if we need all of these (probably not)
    ###############################################################################
    ranks = ['strain', 'species', 'genus', 'family', 'order', 'class', 'phylum', 'superkingdom']

    tsv_md5sum = ""  # result tsv md5sum
    refresh_period = 0  # refresh period in seconds
    banner_div = Div(text="", width=1200)  # default page

    COLORS = RdYlBu11  # RdYlBu11
    GRADIENT = Turbo256
    C_SET1 = Set1[9]
    MIN_SIZE = 10
    MAX_SIZE = 36

    GCOV_CACHE = {}
    BSAT_CACHE = {}
    MASK_CACHE = {}

    bgfiles = []
    bg_mask = {}

    # An alternative to the config_setup() method. Worth investigating as another user-interaction,
    # governed by callbacks within the visualizer itself. Would also make this script slightly neater.
    config_file = join(dirname(__file__), "config.json")

    # Initialize individual object attributes:
    # NOTE: To make routes.py as neat as possible, the majority of methods in this class map to object attributes initialized here.
    def __init__(self, df_full_list, result, sd_strain=['None', 'None'], graph_params=["READ_COUNT_RNR", "SCORE", "RPKM"],  **kwargs):

        self.__dict__.update(kwargs)
        # Global Attributes:
        self.result = result
        self.filepath = result.path
        self.report_df = df_full_list
        self.sd_strain = sd_strain[0]
        self.strain_name = sd_strain[1]
        self.yaxis_parameter = graph_params[0]
        self.color_parameter = graph_params[1]
        self.size_parameter = graph_params[2]

        self.log_text = self.fetch_log_text()
        self.hover = self.define_tooltips()

        # Data Source Attributes:
        self.configs = self.config_setup()
        self.source = self.test_source()
        self.read_info = self.parseLog()  # Fetch relevant log info for piecharts

        # Figure-Specific Attributes:
        self.dotplot = self.dotplot_skeleton()
        self.piechart_list = self.piechart_sources()
        self.datatable = self.construct_dt()
        self.scaledown = self.construct_scaledown()

        # Not working - try writing a method that literally returns strings from these parameters?
        # Figure Parameter Attributes:

    ###############################################################################
    # DataSource Construction - Used in all Figure Methods:
    ###############################################################################

    # This method creates self.source and fills out source.data, which are both used in many other places by this class.
    # Note that self.source and it's attribute source.data map directly to the .tsv file produced by PanGIA.
    def test_source(self):

        df_sources = self.report_df
        y_axis = str(self.yaxis_parameter)
        color = str(self.color_parameter)
        size = str(self.size_parameter)
        sources = []
        for df in df_sources:

            df["REL_ABUNDANCE"] = df["REL_ABUNDANCE"] + 0.001

            # Set up all user-adjustable parameters:
            df["TRUE_Y"] = df[y_axis]

            # We make an effort to normalize the size/color values here - the "radius" option for glyph size can easily
            # blow up way too big - but in exchange it prevents data from being so small as to be invisible on the plot.
            # Normalizing between zero and one is okay - but when zoomed in on just one or two points, a glyph size = 1
            # is still a bit too large - so better would be a normalized value between 0 and 0.8, maybe.
            df["TRUE_COLOR"] = ((df[color] - df[color].min()) / (df[color].max() - (df[color].min())))
            df["TRUE_SIZE"] = (((df[size] - df[size].min()) / (df[size].max() - (df[size].min()))) / 2)


            # Create the Bokeh source object:
            source = ColumnDataSource()
            source.data = {}
            source.data = dict(

                # Name and Level:
                taxa=df["NAME"].tolist(),
                taxid=[str(x).replace(".0", "") for x in df["TAXID"].values],
                rank_level=df["LEVEL"].to_list(),

                # Counts:
                raw_rd_cnt=df["READ_COUNT"].to_list(),
                tol_genome_sz=df["TOL_GENOME_SIZE"].to_list(),
                relative_abun=df["REL_ABUNDANCE"].to_list(),  # ra: 'relative abundance'

                # Scoring:
                min_score=df["SCORE"].to_list(),
                score_bg=df["SCORE_BG"].tolist() if 'SCORE_BG' in df else [None] * len(c),
                # bg: 'background'
                score_uniq=df["SCORE_UNIQ"].to_list(),  # score_uniq: 'score based on phylogenic uniqueness'

                # Normalized Data:
                norm_rd_cnt=df["READ_COUNT_RNR"].to_list(),  # rnr: 'normalized read count'
                min_norm_rd_cnt_combo=df["READ_COUNT_RSNB"].to_list(),
                # rsnb: 'normalized & combined (primary + secondary hits) read count'
                read_primary=df["PRI_READ_COUNT"].to_list(),  # pri: 'primary read'
                rpkm=df["RPKM"].to_list(),  # rpkm: 'reads per kilobase per million mapped reads'

                # Coverage-Specific Data:
                linear_len=df["LINEAR_LENGTH"].to_list(),  # lnr_len: 'linear length'
                min_linear_cov=df["LINEAR_COV"].to_list(),  # lnr_cov: 'linear coverage'
                rankspec_min_depth_cov=df[
                    "RS_DEPTH_COV_NR"].to_list() if "RS_DEPTH_COV_NR" in df else [None] * len(c),
                # rsdcnr: 'normalized rank specific depth-of-coverage'
                min_depth_cov=df["DEPTH_COV"].to_list(),  # depth_cov: 'depth-of-coverage'

                # Rank-Specific Data:
                strain=df["STR"].to_list(),
                species=df["SPE"].to_list(),
                genus=df["GEN"].to_list(),
                family=df["FAM"].to_list(),
                order=df["ORD"].to_list(),
                clade=df["CLA"].to_list(),
                phylum=df["PHY"].to_list(),
                superkingdom=df["SK"].to_list(),
                root=df["ROOT"].to_list(),

                # Normalized Rank-Specific Data:
                strain_rnr=df['STR_rnr'].to_list(),
                species_rnr=df['SPE_rnr'].to_list(),
                genus_rnr=df['GEN_rnr'].to_list(),
                family_rnr=df['FAM_rnr'].to_list(),
                order_rnr=df['ORD_rnr'].to_list(),
                clade_rnr=df['CLA_rnr'].to_list(),
                phylum_rnr=df['PHY_rnr'].to_list(),
                superkingdom_rnr=df['SK_rnr'].to_list(),
                root_rnr=df['ROOT_rnr'].to_list(),

                # Normalized + Combined (Primary + Secondary) Rank-Specific Data:
                strain_rnb=df['STR_rnb'].to_list(),
                species_rnb=df['SPE_rnb'].to_list(),
                genus_rnb=df['GEN_rnb'].to_list(),
                family_rnb=df['FAM_rnb'].to_list(),
                order_rnb=df['ORD_rnb'].to_list(),
                clade_rnb=df['CLA_rnb'].to_list(),
                phylum_rnb=df['PHY_rnb'].to_list(),
                superkingdom_rnb=df['SK_rnb'].to_list(),
                root_rnb=df['ROOT_rnb'].to_list(),

                # Rank-Specific Taxonomic Specificity Level Data:
                strain_ri=df['STR_ri'].to_list() if 'STR_ri' in df else [None] * len(c),
                species_ri=df['SPE_ri'].to_list() if 'SPE_ri' in df else [None] * len(c),
                genus_ri=df['GEN_ri'].to_list() if 'GEN_ri' in df else [None] * len(c),
                family_ri=df['FAM_ri'].to_list() if 'FAM_ri' in df else [None] * len(c),
                order_ri=df['ORD_ri'].to_list() if 'ORD_ri' in df else [None] * len(c),
                clade_ri=df['CLA_ri'].to_list() if 'CLA_ri' in df else [None] * len(c),
                phylum_ri=df['PHY_ri'].to_list() if 'PHY_ri' in df else [None] * len(c),
                superkingdom_ri=df['SK_ri'].to_list() if 'SK_ri' in df else [None] * len(c),
                root_ri=df['ROOT_ri'].to_list() if 'ROOT_ri' in df else [None] * len(c),

                # Pathogen-Specific Data:
                patho_host=df["HOST"].to_list(),  # p_host: name of a pathogen's host
                #           patho_origin           = self.report_df["p_src"].to_list(), #p_src: source organism of given pathogen
                patho_location=df["LOCATION"].to_list(),  # p_loc: (genomic) location of given pathogen
                patho_disease=df["DISEASE"].to_list(),  # p_dse: disease(s) caused by given pathogen
                pathogen=["Yes" if x == "Pathogen" else "No" for x in df['PATHOGEN'].values],

                # Parameterization Values:
                yaxis_param=df["TRUE_Y"].to_list(),
                color_param=df["TRUE_COLOR"].to_list(),
                size_param=df["TRUE_SIZE"].to_list()
            )

            sources.append(source)

        # Current State: I appear to be creating three separate ColumnDataSources and can return them.
        # The effects appear to be working downstream in FactorRange.
        return sources

    ###############################################################################
    # Figure Construction - Dotplot, Piecharts, and DataTable:
    ###############################################################################

    ######
    ###### CONSTRUCT DOTPLOT:
    ######

    # Constructs a dotplot centered in our webpage - the "main attraction" as it were.
    def dotplot_skeleton(self):

        # I'd like to instantiate a dictionary that keys the shorthand column labels to more intelligible, user-friendly
        # labels - so "norm_rd_cnt":"Normalized Read Count", for example.

        df_sources = self.report_df

        # We pull these values in for use in the return_key() method below - it's how we'll access keys for labeling.
        cur_df = df_sources[0]
        y_axis = str(self.yaxis_parameter)
        color = str(self.color_parameter)

        # Construct the dotplots. It's been implemented in this "array-like" format for modularity.
        # With this method, we can make our class more flexible, adding graphs as needed to this function.
        dotplot_list = []
        for i in range(len(self.source)):
            source = self.source[i]
            dot_hover = self.hover[0]
            view = CDSView(source=source)
            x_range = FactorRange(*source.data["taxa"])
            min_color = min(source.data['color_param'])
            max_color = max(source.data['color_param'])

            # We use customizable parameters for color, size, and y-axis - see source.data!
            color_map = linear_cmap(field_name='color_param', palette=Turbo256, low=min_color,
                                high=max_color)

            # Configs are used to define the size of our new window. This may need changing for compatibility with
            # the in-window approach used by Real-Time PanGIA.
            dotplot = figure(plot_width=1400,
                         plot_height=self.configs['displays']['dot_plot_height'],
                         x_range=x_range, y_range=(0, max(source.data['yaxis_param'])),
                         output_backend=self.configs['displays']['output_backend'],
                         tools=["wheel_zoom, box_zoom, reset, tap", dot_hover],
                         sizing_mode="stretch_width"
                         )

            # To get the correct labels for our color-bar and y-axis, we must extract appropriate keys from source.data:
            def return_key(val):
                for key, value in source.data.items():
                    if value == val:
                        return key

            min_color_str = str(min_color)
            max_color_str = str(max_color)
            color_label = return_key(cur_df[color].to_list()) + " True Min: " + min_color_str + " True Max: " + max_color_str + "---  Normalized Between 0 and 1"

            y_axis_label = return_key(cur_df[y_axis].tolist())

            color_bar = ColorBar(color_mapper=color_map['transform'], width=20, label_standoff=12, title=color_label,
                             title_text_align='left', title_text_font_size='12px')

            dotplot.add_layout(color_bar, 'right')

            dotplot.xaxis.axis_label = "Taxa"
            dotplot.xaxis.major_label_orientation = 3.1415926 / 4
            dotplot.yaxis.axis_label = y_axis_label
            dotplot.background_fill_color = "beige"
            dotplot.background_fill_alpha = 0.5
            dotplot.outline_line_width = 6
            dotplot.outline_line_alpha = 0.1
            dotplot.outline_line_color = "navy"
            dotplot.x_range.range_padding = 0

            dotplot.circle(x=dodge('taxa', 0.0, range=dotplot.x_range), y="yaxis_param", source=source, view=view, radius="size_param", color=color_map,
                       line_color=color_map,
                       fill_alpha=0.6, line_alpha=0.7)

            # To make color_bar adjustable, the title needs to be populated by the call to JSCallback.
            # See class methods js_link() and js_on_change() for help.

            dotplot_list.append(dotplot)

        return dotplot_list

    ######
    ###### CONSTRUCT PIECHARTS:
    ######

    def piechart_sources(self):

        pieHover = self.hover[1]

        ######
        ###### CONSTRUCT PIECHART DATA SOURCES:
        ######

        ###### Pie Chart Data Source Build:
        # Because our piecharts are constructed differently from dotplot, we must specify both source and source.data here.
        # We opted to construct source.data for each by referencing the index of a list, called 'pievalue_list', returned by a method in the 'Supporting Methods' section.
        pieInReadsDS = ColumnDataSource(
            data=dict(name=['NA'], start_angle=[0], end_angle=[2 * pi], color=['#EFF0F1'], val=['NA'], pct=['NA']))
        pieFlagDS = ColumnDataSource(
            data=dict(name=['NA'], start_angle=[0], end_angle=[2 * pi], color=['#EFF0F1'], val=['NA'], pct=['NA']))
        piePathoDS = ColumnDataSource(
            data=dict(name=['NA'], start_angle=[0], end_angle=[2 * pi], color=['#EFF0F1'], val=['NA'], pct=['NA']))

        ###### In-Reads Data Source:

        logfile = self.read_info
        pievalue_list = self.genPieValues(logfile)
        pieInReadsDS.data = dict(
            name=pievalue_list[0], start_angle=pievalue_list[1], end_angle=pievalue_list[2],
            color=pievalue_list[3], val=pievalue_list[4], pct=pievalue_list[5])

        ###### Pathos Data Source:

        info = {}
        info['Pathogen'] = self.report_df[0].loc[self.report_df[0].PATHOGEN == "Pathogen", "PRI_READ_COUNT"].sum()
        info['Not pathogen'] = self.report_df[0].loc[:, "PRI_READ_COUNT"].sum() - info['Pathogen']
        pievalue_list = self.genPieValues(info)
        piePathoDS.data = dict(
            name=pievalue_list[0], start_angle=pievalue_list[1], end_angle=pievalue_list[2],
            color=pievalue_list[3], val=pievalue_list[4], pct=pievalue_list[5])

        ###### Flag Data Source:

        if "FLAG" in self.report_df[0]:
            info = {}
            for flag in self.report_df[0].FLAG.unique():
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

                info[name] = self.report_df[0].loc[self.report_df[0].FLAG == flag, "PRI_READ_COUNT"].sum()

            pievalue_list = self.genPieValues(info)

            pieFlagDS.data = dict(
                name=pievalue_list[0], start_angle=pievalue_list[1], end_angle=pievalue_list[2],
                color=pievalue_list[3], val=pievalue_list[4], pct=pievalue_list[5])

        ######
        ###### BUILD OUT PIECHARTS:
        ######

        ###### Log File In-Reads Pie Chart:
        pieInReadsFigure = figure(
            x_range=(-1.3, 4),
            output_backend=self.configs['displays']['output_backend'],
            y_range=(-2, 2),
            plot_width=self.configs['displays']['dashboard_pie_width'],
            plot_height=self.configs['displays']['dashboard_pie_height'],
            title="Total reads:",
            tools=[self.hover[1]]
        )

        pieInReadsFigure.annular_wedge(
            x=0, y=0, alpha=0.7,
            legend_field='name', start_angle='start_angle', end_angle='end_angle', color='color',
            inner_radius=0.7, outer_radius=1.2, source=pieInReadsDS
        )

        ###### Flag Distribution Piechart:
        pieFlagFigure = figure(
            x_range=(-1.5, 4),
            y_range=(-2, 2),
            plot_width=self.configs['displays']['dashboard_pie_width'],
            plot_height=self.configs['displays']['dashboard_pie_height'],
            title="Target reads distribution:",
            tools=[self.hover[1]]
        )

        pieFlagFigure.annular_wedge(
            x=0, y=0, alpha=0.7,
            legend_field='name', start_angle='start_angle', end_angle='end_angle', color='color',
            inner_radius=0.7, outer_radius=1.2, source=pieFlagDS
        )

        ###### Pathogen Stats Piechart:
        piePathoFigure = figure(
            x_range=(-1.27, 4),
            output_backend=self.configs['displays']['output_backend'],
            y_range=(-2, 2),
            plot_width=self.configs['displays']['dashboard_pie_width'],
            plot_height=self.configs['displays']['dashboard_pie_height'],
            title="Pathogen reads distribution:",
            tools=[self.hover[1]]
        )

        piePathoFigure.annular_wedge(
            x=0, y=0, alpha=0.7,
            legend_field='name', start_angle='start_angle', end_angle='end_angle', color='color',
            inner_radius=0.7, outer_radius=1.2, source=piePathoDS
        )

        ######
        ###### RETURN FORMATTED PIECHARTS:
        ######

        piechart_list = [pieInReadsFigure, pieFlagFigure, piePathoFigure]

        for chart in piechart_list:
            chart.axis.visible = False
            chart.grid.visible = False
            chart.legend.location = "center_right"
            chart.toolbar.logo = None
            chart.toolbar_location = None
            chart.outline_line_width = 1
            chart.outline_line_alpha = 1

        return piechart_list

    ######
    ###### CONSTRUCT DATA TABLE:
    ######

    def construct_dt(self):
        result_table_list = []
        for i in range(len(self.source)):
            source = self.source[i]

            table_cols = [
                TableColumn(field="taxa", title="Name", width=800),
                TableColumn(field="rank_level", title="Rank"),
                TableColumn(field="norm_rd_cnt", title="Normalized Read Count", formatter=NumberFormatter(format='0,0.00')),
                TableColumn(field="min_norm_rd_cnt_combo", title="Normalized & Combined Read Count",
                            formatter=NumberFormatter(format='0,0.00')),
                TableColumn(field="read_percent_id", title="Read Percent Identity",
                            formatter=NumberFormatter(format='0,0')),
                TableColumn(field="min_score", title="Score", formatter=NumberFormatter(format='0.00')),
                TableColumn(field="score_uniq", title="Score (Unique)", formatter=NumberFormatter(format='0.00')),
                TableColumn(field="score_bg", title="Score (Background)", formatter=NumberFormatter(format='0.00')),
                TableColumn(field="rpkm", title="(Reads/kb)/1M Mapped Reads", formatter=NumberFormatter(format='0,0')),
                TableColumn(field="min_linear_cov", title="Genome Coverage", formatter=NumberFormatter(format='0,0.00')),
                TableColumn(field="rankspec_min_depth_cov", title="Normalized Rank-Specific Depth-of-Coverage",
                            formatter=NumberFormatter(format='0,0.00')),
                TableColumn(field="min_depth_cov", title="Depth-of-Coverage", formatter=NumberFormatter(format='0,0.00')),
                TableColumn(field="relative_abun", title="Relative Abundance", formatter=NumberFormatter(format='0.00%')),
                TableColumn(field="pathogen", title="Pathogen"),
                ]

            data_table = DataTable(
                source=source,
                columns=table_cols,
                index_position=None,
                width=1400,
                height=200
                )
            result_table = column(data_table)
            result_table_list.append(result_table)

        return result_table_list

    def construct_scaledown(self):

        # Create hovertools for scaledown plots - consider bringing these down to the hover method
        hover_gcov = HoverTool(tooltips=[
            ("Depth", "information"),
            ("Reference", "@gc_ref"),
            ("Position", "@gc_pos"),
            ("Depth", "@gc_dep")],
            names=['b_gcov'],
            mode='vline'
        )

        hover_bsat = HoverTool(tooltips=[
            ("Marker", "information"),
            ("Reference", "@b_ref"),
            ("Location", "@b_str..@b_end"),
            ("Note", "@b_not")],
            names=['b_bsat'],
            mode='vline'
        )

        # Set up empty sources.
        gcov_source = ColumnDataSource(data=dict(
            gc_ref=[],
            gc_pos=[],
            gc_dep=[],
            gc_col=[]
        ))

        bsat_source = ColumnDataSource(data=dict(
            b_ref=[],
            b_str=[],
            b_end=[],
            b_col=[],
            b_not=[],
        ))

        # Set up scaledown source and required strain info.
        sd_source = self.source[0]
        sd_strain = self.sd_strain
        strain_name = self.strain_name

        # Use strain name if sd_strain exists:
        if sd_strain == 'None':
            graph_titles = 'Not available at this rank (strain only)'
        else:
            graph_titles = "Strain: " + strain_name + " | Taxid: " + str(sd_strain) + " | Zoom in to use the hovertool!"

        # Create empty scaledown plots to be populated:
        coverage_p_lin = figure(
            plot_width=2000,
            plot_height=self.configs['displays']['gcov_plot_height'],
            min_border=0,
            y_axis_label='Depth (x)',
            output_backend=self.configs['displays']['output_backend'],
            title=graph_titles,
            tools=["wheel_zoom,box_zoom,pan,reset,save", hover_gcov, hover_bsat]
        )

        coverage_p_log = figure(
            plot_width=2000,
            plot_height=self.configs['displays']['gcov_plot_height'],
            min_border=0,
            y_axis_label='Depth (x)',
            output_backend=self.configs['displays']['output_backend'],
            y_axis_type="log",
            title=graph_titles,
            tools=["wheel_zoom,box_zoom,pan,reset,save", hover_gcov, hover_bsat]
        )

        coverage_p_log.y_range.start = 0.1
        coverage_p_lin.y_range.start = 0
        coverage_p_log.x_range.start = 0
        coverage_p_lin.x_range.start = 0

        if sd_strain == 'None':
            return [coverage_p_lin, coverage_p_log]
        sd_file = self.filepath + "/" + str(sd_strain) + ".depth.scaledown"

        # Read in scaledown results into a dataframe - then eliminate dupes for the coverage plot.
        sd_gcov_df = pd.read_csv(sd_file, sep='\t', header=None, names=['ref', 'pos', 'dep'])
        sd_gcov_df = sd_gcov_df.drop_duplicates(subset=['ref', 'pos'])

        # Reference colors? I may need to bring in color bar or gradient here, as before.
        coverage_color = {}
        coverage_names = sd_gcov_df['ref'].unique().tolist()
            # Add some color here based on all the unique values, and assign to dict. Then referencd later, I think?

        gcov_source.data = dict(
            gc_ref = sd_gcov_df['ref'].to_list(),
            gc_pos = sd_gcov_df['pos'].to_list(),
            gc_dep = sd_gcov_df['dep'].to_list()
        )

        # Baseline axes in scaledown COVERAGE plots:
        coverage_p_log.vbar(x='gc_pos', top='gc_dep', width=1, bottom=0.1, alpha=0.2, name="b_gcov",
                            source=gcov_source)
        coverage_p_lin.vbar(x='gc_pos', top='gc_dep', width=1, bottom=0, alpha=0.2, name="b_gcov",
                            source=gcov_source)

        max_gc_dep = max(gcov_source.data['gc_dep'])
        coverage_p_log.y_range.end = max_gc_dep*3
        coverage_p_lin.y_range.end = max_gc_dep*1.1

        note_color = {} # Might need some kind of color making here.
        offset = 1
        bsat = dict(b_ref=[], b_str=[], b_end=[], b_col=[], b_not=[])

        for gc_ref in sd_gcov_df['ref'].unique().tolist():
            (acc, leng, taxid, tag) = gc_ref.split('|')

            bsat_fn = f"{self.filepath}/{acc}.bsat.bed"
            if not os.path.isfile(bsat_fn):
                bsat_fn = f"{db_path}/BSAT_markers/{acc}.bsat.bed"
                pass

            if os.path.isfile(bsat_fn) and os.path.getsize(bsat_fn) > 0:
                coverage_p_log.title.text = f"Loading BSAT coordinates for {gc_ref}..."
                coverage_p_lin.title.text = f"Loading BSAT coordinates for {gc_ref}..."
                # loading coverage files
                bsat_df = pd.read_csv(bsat_fn, sep='\t', header=None, names=['ref', 'str', 'end', 'note'])
                # pu = pu.drop_duplicates(subset=['ref', 'str', 'end'])
                bsat['b_ref'] += [gc_ref for x in bsat_df['note'].tolist()]
                bsat['b_str'] += (bsat_df['str'] + offset).tolist()
                bsat['b_end'] += (bsat_df['end'] + offset).tolist()
                bsat['b_col'] += [note_color[x] for x in bsat_df['note'].tolist()]
                bsat['b_not'] += bsat_df['note'].tolist()

            offset += int(leng)
            bsat_source.data = bsat

        # Begin adjusting axes and data in scaledown COVERAGE plots:
        coverage_p_lin.x_range.start = min(gcov_source.data['gc_pos']) - 0.1*min(gcov_source.data['gc_pos'])
        coverage_p_log.x_range.start = min(gcov_source.data['gc_pos']) - 0.1*min(gcov_source.data['gc_pos'])
        coverage_p_lin.x_range.end = max(gcov_source.data['gc_pos']) + 0.1*max(gcov_source.data['gc_pos'])
        coverage_p_log.x_range.end = max(gcov_source.data['gc_pos']) + 0.1*max(gcov_source.data['gc_pos'])

        # additional y-range
        coverage_p_log.extra_y_ranges = {"BSAT": Range1d(start=0.1, end=10)}
        coverage_p_lin.extra_y_ranges = {"BSAT": Range1d(start=0, end=10)}

        # BSAT
        coverage_p_log.hbar(left='b_str', right='b_end', y=0.3, height=0.13, source=bsat_source,
                            name="b_bsat", y_range_name="BSAT")
        coverage_p_lin.hbar(left='b_str', right='b_end', y=2.3, height=1.0, source=bsat_source,
                            name="b_bsat", y_range_name="BSAT")


        coverage_p_log.toolbar.logo = None
        coverage_p_lin.toolbar.logo = None

        ds_plots = []
        ds_plots.append(coverage_p_lin)
        ds_plots.append(coverage_p_log)
        # TEMP TESTING --- PRINT IN ROUTES
        ds_plots.append(sd_gcov_df)
        ds_plots.append(sd_source)

        return ds_plots

    ###############################################################################
    # Custom JavaScript Callback Methods
    ###############################################################################

    # All JS Callbacks require a dictionary called "controls" - it isn't clear whether a single "controls" dictionary with everything
    # in it will do, or if we need a method that returns a different dictionary each time it is called, customized for each JS callback event.
    # In the example, the "new data" seemed ready to accept everything in source.

#    def control_change(self):

#        return


    ###############################################################################
    # Supporting Methods:
    ###############################################################################

    ######
    ###### INIT METHODS:
    ######

    # A method used to load a config file, which could maybe be changed in GUI settings.
    # Presently relies on hardcoding to load config_file from a JSON/Manually create config dictionary.
    def check_config(config_file=config_file):
        try:
            config_json = open(config_file, 'r').read()
            config = json.loads(config_json)
            return logconfig.bokeh_logger.debug(f"[INFO] [CONFIG] {config_file} loaded.")
        except:
            return logconfig.bokeh_logger.debug(f"[INFO] [CONFIG] {config_file} NOT loaded.")

    # A method that expects a call to Results to populate the argument with a filepath.
    def fetch_report_df(self):
        for file in os.scandir(self.filepath):
            if '.report.tsv' in Path(file).name:
                df = pd.read_csv(file, sep='\t')
                df = df[df['LEVEL'].isin(['genus', 'species'])]
                df['REL_ABUNDANCE'] = df['REL_ABUNDANCE']
                df_species = df[df['LEVEL'].isin(['species'])]
                df_genus = df[df['LEVEL'].isin(['genus'])]
                df_ranksep_list = [df_species, df_genus]
                df_full = pd.concat(df_ranksep_list)
                df_full_list = [df_full, df_species, df_genus]
                # Adding a way to return the original tsv as well.
                all_files = [file, df_full_list]
                return all_files

    # This method also expects a call to Results, but instead on the logfile produced in the PanGIA run.
    def fetch_log_text(self):
        for file in os.scandir(self.filepath):
            if '.pangia.log' in Path(file).name:
                with open(file, 'r') as f:
                    log = f.read()
                    return log

    ######
    ###### PIE CHART SUPPORTING METHODS:
    ######

    # Becaue the in-reads piechart is constructed base on information stored in the logfile
    # (instead of the .tsv), we use this method to get counts of the reads from 'target', 'host', and 'ignored'.
    def parseLog(self):
        total_input = 0
        total_mapped = 0
        info = {}
        info['Target'] = 0
        info['Host'] = 0
        info['Ignored'] = 0

        for file in os.scandir(self.filepath):
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

    # Called by the big pie-chart method to pull in the correct values to return to data.source;
    # This can be either from the logfile - see parseLog() - or from self.source!
    def genPieValues(self, infodict):
        tol_cnt = 0
        ang_start = 0
        ang_size = 6.27
        colors = list(itemgetter(9, 3, 0, 1, 2, 5, 7, 8, 9)(Spectral11))

        p_name, p_str_ang, p_stp_ang, p_col, p_val, p_pct = [], [], [], [], [], []

        for name in infodict:
            p_val.append(infodict[name])
            tol_cnt += infodict[name]

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
        for value in pievalue_list:
            print(value)

        return pievalue_list

    ######
    ###### HOVERTOOL METHODS:
    ######

    # Define what the text-pop ups will say when hovering over a given value.
    # Note the one-to-one correspondance to variable names in source.data (from self.source).
    # These tools are instantiated by adding a 'tools=[]' argument to figure construction.
    def define_tooltips(self):
        hoverlist = []
        hover_graph = HoverTool(tooltips=[
            ("Name", "@taxa"),
            ("TaxID", "@taxid"),
            ("Score", "@min_score{0.00}"),
            ("Linear Coverage", "@min_linear_cov{0,0.00}"),
            ("Depth-of-Coverage", "@min_depth_cov{0,0.00}"),
            ("Normalized Rank-Specific Depth-of-Coverage (RSNR)", "@rankspec_min_depth_cov{0,0.00}"),
            ("Relative Abundance", "@relative_abun{0,0.00}"),
            ("Raw Read Count", "@raw_rd_cnt{0,0}"),
            ("Normalized Read Count", "@norm_rd_cnt{0,0.00}"),
            ("Normalized Rank-Specific Read Count)", "@norm_rd_cnt_combo{0,0.00}"),
            ("Primary Read", "@read_primary{0,0}"),
            ("RPKM", "@rpkm{0,0.00}"),
            ("Score (Unique)", "@score_uniq{0.00}"),
            ("Score (Background)", "@score_bg{0.00}"),
            ("Genome Size (bp)", "@tol_genome_sz{0,0}"),
            ("Pathogen", "@pathogen"),
        ],
            mode='vline'
        )

        pie_hover = HoverTool(tooltips=[("Name", "@name"),
                                        ("Reads", '@val{,} (@pct{%0.0f})')
                                        ])

        hoverlist = [hover_graph, pie_hover]
        return hoverlist

    #######
    ####### SET UP DEFAULT CONFIGURATIONS - FIGURE SIZE & TEXT COMPONENTS
    #######

    def config_setup(self):

        # Is any of this necessary if the .json file is being loaded?!?
        config = {}
        config['cutoffs'] = {}

        #config = {'cutoffs' : {'def_val_patho' : True, 'def_val_min_len' : 50, }, 'displays' : {'total_width' : 1070, }}

        config['cutoffs']['def_val_patho'] = True  # display mode: 0 -> pathogen only, 1 -> all
        config['cutoffs']['def_val_min_len'] = 50  # Minimum linear length [0-500] step=1
        config['cutoffs']['def_val_min_cov'] = 0.01  # Minimum genome coverage [0-1] step=0.01
        config['cutoffs']['def_val_max_r_raw'] = 100  # Minimum reads [0-500] step=1
        config['cutoffs']['def_val_max_r_rsnb'] = 10  # Minimum reads [0-100] step=1
        config['cutoffs']['def_val_min_score'] = 0.5  # Minimum score [0-1] step=0.1
        config['cutoffs']['def_val_min_dc'] = 10  # Minimum depth coverage MilliX (1X=1000mX) [0-10000] step=10
        config['cutoffs']['def_val_min_rsdc'] = 1  # Minimum rank specific depth coverage in MilliX[0-1000] step=0.001

        config['displays'] = {}
        config['displays']['total_width'] = 1070  # display mode: 0 -> pathogen only, 1 -> all
        config['displays']['dot_plot_width'] = 800  # Minimum linear length [0-500] step=1
        config['displays']['dot_plot_height'] = 800  # display mode: 0 -> pathogen only, 1 -> all
        config['displays']['gcov_plot_width'] = 1060  # display mode: 0 -> pathogen only, 1 -> all
        config['displays']['gcov_plot_height'] = 190  # display mode: 0 -> pathogen only, 1 -> all
        config['displays']['read_plot_width'] = 270  # display mode: 0 -> pathogen only, 1 -> all
        config['displays']['read_plot_height'] = 210  # display mode: 0 -> pathogen only, 1 -> all

        config['displays']['dashboard_pie_width'] = int(config['displays']['total_width'] / 2.8)
        config['displays']['dashboard_pie_height'] = int(config['displays']['dashboard_pie_width'] / 380 * 220)

        config['displays']['output_backend'] = 'canvas'  # Minimum linear length [0-500] step=1

        return config
