import json
import os
import ast
from datetime import datetime
import time
from flask import render_template, flash, redirect, url_for, request, g, jsonify, current_app, send_from_directory, \
    send_file, make_response
from flask_login import current_user, login_required
from pathlib import Path
import pandas as pd
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
from markupsafe import Markup
from rq.job import Job
from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource

from json import loads

from app import db
from config import Config
from app.main.forms import AddCategoryForm, AddUserForm, AddFileTemplate, AddMetaType, StartPanGIARun, StartRealTime, \
    ChangePanGIASettings
from app.models import User, Role, MetaTemplate, MetaType, MetaTypeToTemplates, Metadata, Category, Item, Results, \
    ResultsToItem, Task

from app.bokeh_class import BokehObject
from bokeh.embed import components
from bokeh.resources import INLINE
from bokeh.layouts import column, row
from bokeh.models.widgets import Panel, Tabs

# from app.translate import translate
# from flask_babel import _, get_locale
# from guess_language import guess_language
from app.main import bp

basedir = os.path.abspath(os.path.dirname(__file__)).replace('/app/main', '')

# Get Default PanGIA Settings
settings_file = '{}/app/static/scripts/pangia_default_params.csv'.format(basedir)
df = pd.read_csv(settings_file, sep=',', index_col='Field')
settings = df.to_dict()['Value']


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        # g.search_form = SearchForm()
    # g.locale = str(get_locale())


# ----------------------------------------------------------------------------------------------------------------------
# ADD EXTRA CONTEXT PROCESSORS TO TEMPLATES
# ----------------------------------------------------------------------------------------------------------------------
@bp.context_processor
def projects():
    projects = Category.query.filter_by(parent_id=0, is_archived=False, is_deleted=False)
    return {'projects': projects}


# ----------------------------------------------------------------------------------------------------------------------
# ADD EXTRA CONTEXT PROCESSORS TO TEMPLATES
# ----------------------------------------------------------------------------------------------------------------------
@bp.context_processor
def check_admin():
    if 'Admin' in current_user.get_roles():
        return {'is_admin': True}
    else:
        return {'is_admin': False}


'''
@bp.route('/uploads/', methods=['GET'])
def download():

    folder = ''
    for x in request.args.get('dir').split('|'):
        folder += '{}/'.format(x)
    file = request.args.get('f')
    upload_dir = '/gui_flask/PanGIA/uploads/'
    combined_dir = '{}{}'.format(upload_dir, folder)

    combined_dir = combined_dir + file
    return send_from_directory(directory='/gui_flask/PanGIA/uploads/', filename='BA_BL_1.pangia.log', as_attachment=True)

    #return render_template('test.html', test=combined_dir)
'''


# ----------------------------------------------------------------------------------------------------------------------
# DASHBOARD
# ----------------------------------------------------------------------------------------------------------------------
@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    # Beginning my attempt to replace dummy object with real one.
    # Success in retriving currently logged in user and should have access to .db objects related to current user.

    the_user = current_user
    the_user_name = (the_user.fname + ' ' + the_user.lname)
    the_user_results = Results.query.order_by(Results.results_date.desc()).limit(5)

    # Let's do the .split() on the datetime here. Keep the .html as clean as possible.

    #   pangia_runs = []
    pangia_runs_unfinished = Task.query.filter_by(complete=False).order_by(Task.task_date.desc()).all()

    #    for run in current_user.tasks:
    #        if run.get_progress == None:
    #            pangia_runs_unfinished = run.query.order_by(Task.task_date.desc()).limit(5)

    return render_template('main/dashboard.html', title='Welcome to your PanGIA Dashboard!',
                           the_user=the_user,
                           the_user_name=the_user_name,
                           the_user_results=the_user_results,
                           pangia_runs_unfinished=pangia_runs_unfinished
                           )


# ----------------------------------------------------------------------------------------------------------------------
# PROJECT PAGES
# ----------------------------------------------------------------------------------------------------------------------
@bp.route('/project/<proj_slug>', methods=['GET'])
@login_required
def project_page(proj_slug):
    # Project Not Found
    project = Category.query.filter_by(slug=proj_slug).first()
    if not project:
        return redirect(url_for('not_found_error'))

    # Get files and sort  <---- do I need to worry about pagination?
    sort_by = request.args.get('sort')
    if sort_by == 'az_up':
        files = Item.query.filter_by(category_id=project.id, is_deleted=False).order_by(Item.name.asc()).all()
    elif sort_by == 'az_down':
        files = Item.query.filter_by(category_id=project.id, is_deleted=False).order_by(Item.name.desc()).all()
    elif sort_by == 'date_up':
        files = Item.query.filter_by(category_id=project.id, is_deleted=False).order_by(Item.created_on.asc()).all()
    else:
        files = Item.query.filter_by(category_id=project.id, is_deleted=False).order_by(Item.created_on.desc()).all()

    return render_template('main/projects.html', title=project.name, project=proj_slug, files=files)


@bp.route('/project/<proj_slug>/add-file', methods=['GET', 'POST'])
@login_required
def add_file(proj_slug):
    project = Category.query.filter_by(slug=proj_slug).first()
    if not project:
        return redirect(url_for('not_found_error'))

    if request.method == 'POST':

        for f in request.files.getlist("file[]"):  # request.files.items():
            # Strip out non safe characters and spaces from upload files
            filename = secure_filename(f.filename)
            filestem = Path(filename).stem
            ext = Path(filename).suffix
            # Allow uploading gzipped files
            # if ext == '.gz':
            #    ext = filename.split('.')[-2]

            # Get list of templates that include this file type
            meta_temp = MetaTemplate.query.all()

            # If extension in list it can be uploaded
            allowed_ext = []
            for x in meta_temp:
                meta_ext = str(x.file_ext).replace(' ', '').split(',')
                for y in meta_ext:
                    if y not in allowed_ext:
                        allowed_ext.append(y)

            # Upload file and put into database
            if ext in allowed_ext:
                upload_folder = '{}'.format(settings['upload_dir'])
                parent_folder = '{}{}'.format(settings['upload_dir'], proj_slug)
                upload_location = '{}{}/{}'.format(settings['upload_dir'], proj_slug, filename)
                # Make parent directory if it doesn't exist
                if not os.path.exists(upload_folder):
                    os.mkdir(upload_folder)
                if not os.path.exists(parent_folder):
                    os.mkdir(parent_folder)
                # Don't overwrite files <---------- Need to make an option so they can choose to overwrite
                if os.path.exists(upload_location):
                    flash('There is already a file with the name {} in the project {}.'.format(filename, project.name),
                          'warning')
                    return redirect(url_for('main.add_file', proj_slug=proj_slug))
                else:
                    f.save(upload_location)
                    add_file = Item(name=filename, item_path=upload_location, category_id=project.id,
                                    meta_template_id=0)
                    db.session.add(add_file)
                    db.session.commit()
            else:
                txt_allowed_upload = "".join(str("'" + x + "', ") for x in allowed_ext)
                flash('The only allowed files are {} files.'.format(txt_allowed_upload[:-2]), 'warning')
                return redirect(url_for('main.add_file', proj_slug=proj_slug))

            return redirect(url_for('main.add_file_meta', proj_slug=proj_slug))

    return render_template('main/add-file.html', title="Add File", project=proj_slug)


@bp.route('/project/<proj_slug>/add-file-meta', methods=['GET', 'POST'])
@login_required
def add_file_meta(proj_slug):
    project = Category.query.filter_by(slug=proj_slug).first()
    if not project:
        return redirect(url_for('not_found_error'))

    # Add metadata to file upload
    if request.method == 'POST':
        post_args = request.form
        file_id = post_args['file_id']
        template_id = post_args['template_id']
        if Item.query.filter_by(id=file_id).count() == 1:
            # Look through posted metadata and add to database <------ Need to check for required
            for x in post_args:
                if x[:4] == 'meta':
                    this_meta_id = x[5:]
                    this_meta_info = post_args[x]
                    add_meta = Metadata(item_id=file_id, metatype_id=this_meta_id, value=this_meta_info)
                    db.session.add(add_meta)
            # Update file info
            q = Item.query.filter_by(id=file_id).first()
            q.meta_template_id = template_id
            db.session.commit()

    # See if there are any files with missing meta templates if not exit
    if Item.query.filter_by(category_id=project.id, meta_template_id=0).count() < 1:
        return redirect(url_for('main.project_page', proj_slug=proj_slug))

    # Get first uploaded file that doesn't have a meta template
    file = Item.query.filter_by(category_id=project.id, meta_template_id=0).first()
    ext = Path(file.item_path).suffix
    if ext == '.gz':
        ext = str(file.item_path).split('.')[-2]

    # Get templates
    meta_templates = []
    meta_temp = MetaTemplate.query.all()
    for x in meta_temp:
        meta_ext = str(x.file_ext).replace(' ', '').split(',')
        if ext in meta_ext:
            meta_templates.append(x)

    # Get meta fields
    if len(meta_templates) == 1:
        meta_field_ids = []
        for x in meta_templates[0].metatypes:
            meta_field_ids.append(x.metatype_id)

        meta_fields = db.session.query(MetaType).filter(MetaType.id.in_(tuple(meta_field_ids))).all()

        return render_template('main/add-file_meta.html', title="Add File", project=proj_slug, file=file,
                               meta=meta_fields,
                               meta_template=meta_templates[0].id, no_files=False)

    if len(meta_templates) > 1:  # <---------------------------------------------- Need to add multiple template dropdown
        return render_template('main/add-file_meta.html', title="Add File", project=proj_slug, file=file)

    else:
        return redirect(url_for('not_found_error'))


# ----------------------------------------------------------------------------------------------------------------------
# BOKEH VISUALIZATION
# ----------------------------------------------------------------------------------------------------------------------
# When the GET request is made, maintain the last value the user selected for the dropdown menus.
def param_list_popper(param_list, param_element):
    if param_element in param_list:
        param_list.remove(param_element)
        param_list.insert(0, param_element)
    return param_list

@bp.route('/pangia_vis/<results_id>', methods=["GET"])
def vis_button(results_id):

    # Check for GET - if yes, we're pre-filtering on the .tsv:
    if request.method == "GET":
        # Check that there is a result with that id
        check_result = Results.query.filter_by(id=results_id).count()
        if check_result == 0:
            return redirect('main.index')
        else:
            result = Results.query.get(results_id).path
            for file in os.scandir(result):
                graph_params = []
                if '.report.tsv' in Path(file).name:

                    # Set values for controls when the page first opens.
                    df = pd.read_csv(file, sep='\t')

                    raw_rd_count = 0
                    raw_rd_count_label = 0

                    min_linear_cov = 0
                    min_linear_cov_label = 0

                    min_score = 0.5
                    min_score_label = 0.5

                    min_norm_rd_cnt_combo = 0.0
                    min_norm_rd_cnt_combo_label = 0.0

                    min_depth_cov = 0.0
                    min_depth_cov_label = 0.0

                    rankspec_min_depth_cov = 0.0
                    rankspec_min_depth_cov_label = 0.0

                    patho_filter = 'None'
                    ranks = ['species', 'genus', 'strain']

                    df = df.drop_duplicates(subset=['NAME'], keep=False)

                    # Create a list of strain-names for current subset of data (IE - the entire dataset).
                    scaledown_dropdown = df[df['LEVEL'] == 'strain']['NAME'].unique().tolist()
                    sd_strain = 'None'
                    strain_name = 'None'

                    y_param_list = ["READ_COUNT_RNR", "SCORE", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                           "READ_COUNT_RSNB", "RPKM"]
                    color_list = ["SCORE", "READ_COUNT_RNR", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                         "READ_COUNT_RSNB", "RPKM"]
                    size_list = ["RPKM", "SCORE", "READ_COUNT_RNR", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                        "READ_COUNT_RSNB"]
                    y_param = "READ_COUNT_RNR"
                    color_param = "SCORE"
                    size_param = "RPKM"

                    y_param_list = param_list_popper(y_param_list, y_param)
                    color_list = param_list_popper(color_list, color_param)
                    size_list = param_list_popper(size_list, size_param)
                    scaledown_dropdown = param_list_popper(scaledown_dropdown, strain_name)

                    if request.args.get('raw_rd_count') != None:

                        # Pull in GET params for sliders/inputs
                        try:

                            raw_rd_count = int(request.args.get('raw_rd_count'))
                            raw_rd_count_label = int(request.args.get('raw_rd_count_label'))
                            if isinstance(raw_rd_count_label, int) != True:
                                raw_rd_count_label = raw_rd_count

                            min_linear_cov = int(request.args.get('min_linear_cov'))
                            min_linear_cov_label = int(request.args.get('min_linear_cov_label'))
                            if isinstance(min_linear_cov_label, int) != True:
                                min_linear_cov_label = min_linear_cov

                            min_score = float(request.args.get('min_score'))
                            min_score_label = float(request.args.get('min_score_label'))
                            if isinstance(min_score_label, float) != True:
                                min_score_label = min_score

                            min_norm_rd_cnt_combo = float(request.args.get('min_norm_rd_cnt_combo'))
                            min_norm_rd_cnt_combo_label = float(request.args.get('min_norm_rd_cnt_combo_label'))
                            if isinstance(min_norm_rd_cnt_combo_label, float) != True:
                                min_norm_rd_cnt_combo_label = min_norm_rd_cnt_combo

                            min_depth_cov = float(request.args.get('min_depth_cov'))
                            min_depth_cov_label = float(request.args.get('min_depth_cov_label'))
                            if isinstance(min_depth_cov_label, float) != True:
                                min_depth_cov_label = min_depth_cov

                            rankspec_min_depth_cov = float(request.args.get('rankspec_min_depth_cov'))
                            rankspec_min_depth_cov_label = float(request.args.get('rankspec_min_depth_cov_label'))
                            if isinstance(rankspec_min_depth_cov_label, float) != True:
                                rankspec_min_depth_cov_label = rankspec_min_depth_cov

                        except ValueError:

                            raw_rd_count = int(request.args.get('raw_rd_count'))
                            raw_rd_count_label = int(request.args.get('raw_rd_count'))

                            min_linear_cov = int(request.args.get('min_linear_cov'))
                            min_linear_cov_label = int(request.args.get('min_linear_cov'))

                            min_score = float(request.args.get('min_score'))
                            min_score_label = float(request.args.get('min_score'))

                            min_norm_rd_cnt_combo = float(request.args.get('min_norm_rd_cnt_combo'))
                            min_norm_rd_cnt_combo_label = float(request.args.get('min_norm_rd_cnt_combo'))

                            min_depth_cov = float(request.args.get('min_depth_cov'))
                            min_depth_cov_label = float(request.args.get('min_depth_cov'))

                            rankspec_min_depth_cov = float(request.args.get('rankspec_min_depth_cov'))
                            rankspec_min_depth_cov_label = float(request.args.get('rankspec_min_depth_cov'))

                        patho_filter = request.args.get('pathogenic')
                        ranks = request.args.get('rank')

                        sd_strain = str(request.args.get('scaledown_dropdown'))
                        strain_name = sd_strain

                        df_copy = df

                        # Check if pathos is for both genus & species if not just pass one
                        if patho_filter == "Pathogen":
                            df = df[df['PATHOGEN'].isin(['Pathogen'])]
                        elif patho_filter == "No":
                            df = df[df['PATHOGEN'].isnull()]
                        elif patho_filter is None or 'None':
                            flash(" No Pathogen Filter Selected: Defaulting to No Filter ... ")
                            pass

                        # Check if "all" ranks or if just a specific one
                        if ranks == "strain":
                            ranks = ['strain']
                        elif ranks == "species":
                            ranks = ['species']
                        elif ranks == "genus":
                            ranks = ['genus']
                        elif ranks is None:
                            ranks = ['genus', 'species', 'strain']
                            flash(" No Rank-Level Filter Selected: Defaulting to No Filter ... ")

                    # Regular filters - in all cases, decide whether to use label or slider value:
                        df = df[df['LEVEL'].isin(ranks)]

                        if raw_rd_count <= raw_rd_count_label:
                            df = df[df['READ_COUNT'] >= raw_rd_count]
                        else:
                            df = df[df['READ_COUNT'] >= raw_rd_count_label]

                        if min_linear_cov <= min_linear_cov_label:
                            df = df[df['LINEAR_COV'] >= min_linear_cov]
                        else:
                            df = df[df['LINEAR_COV'] >= min_linear_cov_label]

                        if min_score <= min_score_label:
                            df = df[df['SCORE'] >= min_score]
                        else:
                            df = df[df['SCORE'] >= min_score_label]

                        if min_norm_rd_cnt_combo <= min_norm_rd_cnt_combo_label:
                            df = df[df['READ_COUNT_RSNB'] >= min_norm_rd_cnt_combo]
                        else:
                            df = df[df['READ_COUNT_RSNB'] >= min_norm_rd_cnt_combo_label]

                        if min_depth_cov <= min_depth_cov_label:
                            df = df[df['DEPTH_COV'] >= min_depth_cov]
                        else:
                            df = df[df['DEPTH_COV'] >= min_depth_cov_label]

                        if rankspec_min_depth_cov <= rankspec_min_depth_cov_label:
                            df = df[df['RS_DEPTH_COV_NR'] >= rankspec_min_depth_cov]
                        else:
                            df = df[df['RS_DEPTH_COV_NR'] >= rankspec_min_depth_cov_label]

                        df = df.drop_duplicates(subset=['NAME'], keep=False)
                        scaledown_dropdown = df[df['LEVEL'] == 'strain']['NAME'].unique().tolist()

                        try:
                            strain_name = sd_strain
                            sd_strain = df.loc[df['NAME'] == sd_strain, 'TAXID'].iloc[0]
                            if str(sd_strain).split('.')[-1] == '0':
                                sd_strain = str(sd_strain).split('.')[0]
                        except IndexError:
                            sd_strain = 'None'
                            strain_name = 'None'
                        except FileNotFoundError:
                            sd_strain = 'None'
                            flash(" No Scaledown File:  Defaulting to No Rank Filter ... ")
                        if len(df) == 0:
                            df = df_copy
                            flash(" No Data Selected!  Resetting the Dataframe ... ")

                        y_param_list = ["READ_COUNT_RNR", "SCORE", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                        "READ_COUNT_RSNB", "RPKM"]
                        color_list = ["SCORE", "READ_COUNT_RNR", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                      "READ_COUNT_RSNB", "RPKM"]
                        size_list = ["RPKM", "SCORE", "READ_COUNT_RNR", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                     "READ_COUNT_RSNB"]

                        # GET request on the selected axes parameters:
                        y_param = request.args.get('y-axis-parameter')
                        color_param = request.args.get('color-axis-parameter')
                        size_param = request.args.get('size-parameter')

                        # When the GET request is made, maintain the last value the user selected for the dropdown menus.
                        y_param_list = param_list_popper(y_param_list, y_param)
                        color_list = param_list_popper(color_list, color_param)
                        size_list = param_list_popper(size_list, size_param)
                        scaledown_dropdown = param_list_popper(scaledown_dropdown, strain_name)

                    # Check if selections result in an empty dataframe:
                    if len(df) == 0:
                        df = pd.read_csv(file, sep='\t')
                        # Pull in GET params for sliders/inputs
                        raw_rd_count = int(request.args.get('raw_rd_count'))
                        raw_rd_count_label = request.args.get('raw_rd_count_label')
                        if isinstance(raw_rd_count_label, int) != True:
                            raw_rd_count_label = raw_rd_count

                        min_linear_cov = int(request.args.get('min_linear_cov'))
                        min_linear_cov_label = request.args.get('min_linear_cov_label')
                        if isinstance(min_linear_cov_label, int) != True:
                            min_linear_cov_label = min_linear_cov

                        min_score = float(request.args.get('min_score'))
                        min_score_label = request.args.get('min_score_label')
                        if isinstance(min_score_label, float) != True:
                            min_score_label = min_score

                        min_norm_rd_cnt_combo = float(request.args.get('min_norm_rd_cnt_combo'))
                        min_norm_rd_cnt_combo_label = request.args.get('min_norm_rd_cnt_combo_label')
                        if isinstance(min_norm_rd_cnt_combo_label, float) != True:
                            min_norm_rd_cnt_combo_label = min_norm_rd_cnt_combo

                        min_depth_cov = float(request.args.get('min_depth_cov'))
                        min_depth_cov_label = request.args.get('min_depth_cov_label')
                        if isinstance(min_depth_cov_label, float) != True:
                            min_depth_cov_label = min_depth_cov

                        rankspec_min_depth_cov = float(request.args.get('rankspec_min_depth_cov'))
                        rankspec_min_depth_cov_label = request.args.get('rankspec_min_depth_cov_label')
                        if isinstance(rankspec_min_depth_cov_label, float) != True:
                            rankspec_min_depth_cov_label = rankspec_min_depth_cov

                        df = df[df['LEVEL'].isin(ranks)]

                        if raw_rd_count <= raw_rd_count_label:
                            df = df[df['READ_COUNT'] >= raw_rd_count]
                        else:
                            df = df[df['READ_COUNT'] >= raw_rd_count_label]

                        if min_linear_cov <= min_linear_cov_label:
                            df = df[df['LINEAR_COV'] >= min_linear_cov]
                        else:
                            df = df[df['LINEAR_COV'] >= min_linear_cov_label]

                        if min_score <= min_score_label:
                            df = df[df['SCORE'] >= min_score]
                        else:
                            df = df[df['SCORE'] >= min_score_label]

                        if min_norm_rd_cnt_combo <= min_norm_rd_cnt_combo_label:
                            df = df[df['READ_COUNT_RSNB'] >= min_norm_rd_cnt_combo]
                        else:
                            df = df[df['READ_COUNT_RSNB'] >= min_norm_rd_cnt_combo_label]

                        if min_depth_cov <= min_depth_cov_label:
                            df = df[df['DEPTH_COV'] >= min_depth_cov]
                        else:
                            df = df[df['DEPTH_COV'] >= min_depth_cov_label]

                        if rankspec_min_depth_cov <= rankspec_min_depth_cov_label:
                            df = df[df['RS_DEPTH_COV_NR'] >= rankspec_min_depth_cov]
                        else:
                            df = df[df['RS_DEPTH_COV_NR'] >= rankspec_min_depth_cov_label]

                        df = df.drop_duplicates(subset=['NAME'], keep=False)

                        patho_filter = 'None'
                        ranks = ['genus', 'species', 'strain']
                        scaledown_dropdown = df[df['LEVEL'] == 'strain']['NAME'].unique().tolist()
                        scaledown_dropdown = sorted(scaledown_dropdown)

                        # Default Strain Values:
                        strain_name = 'None'
                        sd_strain = 'None'

                        y_param_list = ["READ_COUNT_RNR", "SCORE", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                        "READ_COUNT_RSNB", "RPKM"]
                        color_list = ["SCORE", "READ_COUNT_RNR", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                      "READ_COUNT_RSNB", "RPKM"]
                        size_list = ["RPKM", "SCORE", "READ_COUNT_RNR", "TOL_GENOME_SIZE", "REL_ABUNDANCE",
                                     "READ_COUNT_RSNB"]

                        # Default axes values:
                        y_param = "READ_COUNT_RNR"
                        color_param = "SCORE"
                        size_param = "RPKM"

                        # When the GET request is made, maintain the last value the user selected for the dropdown menus.
                        y_param_list = param_list_popper(y_param_list, y_param)
                        color_list = param_list_popper(color_list, color_param)
                        size_list = param_list_popper(size_list, size_param)
                        scaledown_dropdown = param_list_popper(scaledown_dropdown, strain_name)

                        flash(" There is no data in your selection --- restoring last numerical values ... ")

                    strain_info = [sd_strain, strain_name]
                    graph_params = [y_param, color_param, size_param]
                    df_full_list = [df]

                    # Quick and Dirty max-value enforcement - ensure there is always at least one value:


                    ### SEND FILTERED .TSV TO HTML ###
                    # I may need another filepath to deal with scaledown:
                    max_raw_rd_count = df['READ_COUNT'].max() - (
                            df['READ_COUNT'].max() - df['READ_COUNT'].nlargest(2).min())
                    max_linear_cov = df['LINEAR_COV'].max() - (
                            df['LINEAR_COV'].max() - df['LINEAR_COV'].nlargest(2).min())
                    max_score = df['SCORE'].max() - (df['SCORE'].max() - df['SCORE'].nlargest(2).min())
                    max_norm_rd_cnt_combo = df['READ_COUNT_RSNB'].max() - (
                            df['READ_COUNT_RSNB'].max() - df['READ_COUNT_RSNB'].nlargest(2).min())
                    max_depth_cov = df['DEPTH_COV'].max() - (
                            df['DEPTH_COV'].max() - df['DEPTH_COV'].nlargest(2).min())
                    rankspec_max_depth_cov = df['RS_DEPTH_COV_NR'].max() - (
                            df['RS_DEPTH_COV_NR'].max() - df['RS_DEPTH_COV_NR'].nlargest(2).min())

                    # When the GET request is made, maintain the last value the user selected for the dropdown menus.
                    #y_param_list = param_list_popper(y_param_list, y_param)
                    #color_list = param_list_popper(color_list, color_param)
                    #size_list = param_list_popper(size_list, size_param)
                    #scaledown_dropdown = param_list_popper(scaledown_dropdown, strain_name)

                    bo = BokehObject(df_full_list, Results.query.get(results_id), strain_info, graph_params)

                    dotplot_full = bo.dotplot[0]

                    pieInReads = bo.piechart_list[0]
                    pieFlags = bo.piechart_list[1]
                    piePatho = bo.piechart_list[2]

                    datatable_full = bo.datatable[0]

                    layout_row_piecharts = row([pieInReads, pieFlags, piePatho])
                    layout_row_dotplot_full = row([dotplot_full])

                    # Get the lin/log scaledown plots - returned as a list by bo.
                    ds_lin_tab = Panel(child=bo.scaledown[0], title="Linear")
                    ds_log_tab = Panel(child=bo.scaledown[1], title="Log")
                    scaledown_panel = Tabs(tabs=[ds_lin_tab, ds_log_tab])

                    full_panel = Panel(child=layout_row_dotplot_full, title="Full Dataset")
                    tabs = Tabs(tabs=[full_panel])
                    layout_column = column([layout_row_piecharts, tabs, datatable_full, scaledown_panel])

                    script, div = components(layout_column)

                    # RETURN SECTION:

                    return render_template('items/pangia_vis.html',
                                           plot_script=script, plot_div=div,
                                           js_resources=INLINE.render_js(),
                                           css_resources=INLINE.render_css(),
                                           dotplot=dotplot_full,
                                           datatable=datatable_full,

                                           raw_rd_count=raw_rd_count,
                                           raw_rd_count_label=raw_rd_count_label,

                                           min_linear_cov=min_linear_cov,
                                           min_linear_cov_label=min_linear_cov_label,

                                           min_score=min_score,
                                           min_score_label=min_score_label,

                                           min_norm_rd_cnt_combo=min_norm_rd_cnt_combo,
                                           min_norm_rd_cnt_combo_label=min_norm_rd_cnt_combo_label,

                                           min_depth_cov=min_depth_cov,
                                           min_depth_cov_label=min_depth_cov_label,

                                           rankspec_min_depth_cov=rankspec_min_depth_cov,
                                           rankspec_min_depth_cov_label=rankspec_min_depth_cov_label,

                                           max_raw_rd_count=max_raw_rd_count,
                                           max_linear_cov=max_linear_cov,
                                           max_score=max_score,
                                           max_norm_rd_cnt_combo=max_norm_rd_cnt_combo,
                                           max_depth_cov=max_depth_cov,
                                           rankspec_max_depth_cov=rankspec_max_depth_cov,

                                           patho_filter=patho_filter,
                                           ranks=ranks,

                                           strain_list=scaledown_dropdown,
                                           y_param_list=y_param_list,
                                           color_param_list=color_list,
                                           size_param_list=size_list
                                           )

# ----------------------------------------------------------------------------------------------------------------------
# ITEMS
# ----------------------------------------------------------------------------------------------------------------------
@bp.route('/item/<item_id>')
def item(item_id):
    # Check that there is an item with that id
    check_item = Item.query.filter_by(id=item_id).count()
    if check_item == 0:
        return redirect('main.index')

    # File Results
    tab = request.args.get('p')
    r_id = request.args.get('id')
    item = Item.query.get(item_id)
    if tab == 'results':

        # Go to specific results file
        if r_id and r_id != '':
            check_results = Results.query.filter_by(id=r_id).first()
            check_rtoi = ResultsToItem.query.filter_by(results_id=check_results.id, item_id=item_id).count()
            if check_results and check_rtoi > 0:
                results = Results.query.get(r_id)
                # Get File location
                tsv_file = ''
                log_file = ''
                fastp_file = ''
                for file in os.scandir(results.path):
                    if '.report.tsv' in Path(file).name:
                        tsv_file = file
                    if 'pangia.log' in Path(file).name:
                        log_file = file
                    if 'fastp.html' in Path(file).name:
                        fastp_file = Path(file).absolute()

                        Path(file)

########################################################################################################################

########################################################################################################################

                # Get Report TSV and format
                try:
                    tsv = pd.read_csv(tsv_file, sep='\t', usecols=[
                        'LEVEL',
                        'NAME',
                        'TAXID',
                        'READ_COUNT',
                        'READ_COUNT_RNR',
                        'READ_COUNT_RSNB',
                        'LINEAR_COV',
                        'DEPTH_COV',
                        'REL_ABUNDANCE'
                    ])
                    tsv = tsv[tsv['LEVEL'].isin(['genus', 'species'])]
                except:
                    tsv = ''

                if len(tsv) == 0:
                    tsv_html = 'empty'
                else:
                    tsv_html = Markup(
                        tsv.to_html().replace('class="dataframe"', 'class="table shadow-none border-0"').replace(
                            'border="1"', '').replace('style="text-align: right;"', ''))

                # Get Log file
                with open(log_file, 'r') as f:
                    log_text = f.read()

                params = ast.literal_eval(results.results_param)

                return render_template('items/item_results.html', title='Results', item=item, r_id=r_id,
                                       results=results, params=params, log_text=log_text, tsv_html=tsv_html,
                                       tsv_file=tsv_file, log_file=log_file)

        # Go to results list
        else:
            return render_template('items/item_results_list.html', title='Results List', item=item)

    # File Information
    else:
        return render_template('items/item_info.html', title='File Information', item=item)


@bp.route('/download/<r_id>')
def results_download(r_id):
    print('TEST TESTE TEST TEST ' + str(int(r_id)))
    results = Results.query.get(int(r_id))
    # Get File location
    tsv_file = ''
    log_file = ''

    for file in os.scandir(results.path):
        if '.report.tsv' in Path(file).name:
            tsv_file = Path(file).absolute()
        if 'pangia.log' in Path(file).name:
            log_file = Path(file).absolute()
        # if 'fastp.html' in Path(file).name:
        #    fastp_file = Path(file).absolute()

    # Get TSV and return to user
    if request.args.get('dtsv'):
        return send_file(tsv_file, as_attachment=True, attachment_filename=Path(tsv_file).name)
    # Get Log and return to user
    if request.args.get('dlog'):
        return send_file(log_file, as_attachment=True, attachment_filename=Path(log_file).name)

    # return render_template('test.html', results=results, tsv_file=tsv_file, log_file=log_file)


# ----------------------------------------------------------------------------------------------------------------------
# PANGIA AND PANGIA ACTIONS
# ----------------------------------------------------------------------------------------------------------------------
@bp.route('/pangia')
def pangia():
    queue_len = Task.query.filter_by(complete=False).order_by(Task.task_date.desc()).count()
    queue = Task.query.filter_by(complete=False).order_by(Task.task_date.desc()).all()
    results = Results.query.order_by(Results.results_date.desc()).all()

    return render_template('pangia/pangia.html', title="PanGIA", queue=queue, queue_len=queue_len, results=results)


@bp.route('/pangia/processing/<task_id>')
def pangia_processing(task_id):
    t = Task.query.get(task_id)

    log_text = ''
    if t.complete == False:
        options = ast.literal_eval(t.options)
        log_file = '{}/{}.pangia.log'.format(options['tmp_dir'], options['file_stem'])
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_text = f.read()

        return render_template('pangia/pangia_processing.html', task=t, options=options, log_text=log_text)
    else:
        flash('{} has finished processing.'.format(t.name), 'success')
        return redirect(url_for('main.pangia'))

# This requires total rework.

@bp.route('/real_time/processing/<task_id>', methods=['GET'])
def real_time_processing(task_id):
    t = Task.query.get(task_id)

    if t.complete == False:

        options = ast.literal_eval(t.options)

        run_bokeh = True
        check_db = 0
        tsv_length = 0

        tsv_file, log_file, fastp_file = '','',''

        try:
            # Make sure there is a result and make a plot
            check_db = Results.query.filter_by(id=options['results_id']).count()
            result = Results.query.get(options['results_id'])
            for file in os.scandir(result.path):
                if '.report.tsv' in Path(file).name:
                    tsv_file = Path(file).absolute()
                    tsv_length = len(pd.read_table(tsv_file))

        except:
            run_bokeh = False

        if check_db == 0:
            run_bokeh = False
        if tsv_length == 0:
            run_bokeh = False

        # Found this task and tsv has results
        if run_bokeh != False:

            return render_template('pangia/real_time_processing_test.html',
            title='Results',
            task=t,
            tsv_file = tsv_file,
            results = result
            )

        # Empty tsv
        else:
            return render_template('pangia/real_time_processing_test.html',
            title='Results',
            task=t,
            tsv_file = '',
            results = ''
            )

    # Process Finished
    else:
        return redirect(url_for('main.pangia'))


@bp.route('/kill_job/<task_id>')
def kill_job(task_id):
    t = Task.query.get(task_id)
    t.kill_job()

    flash('{} job has been stopped.'.format(t.name), 'success')
    return redirect(url_for('main.pangia'))


@bp.route('/pangia_start', methods=['GET', 'POST'])
def pangia_start():
    global settings
    global settings_file

    for key in settings:
        if settings[key] in ['True', 'true', 'Yes', 'yes'] and settings[key] != 1:
            settings[key] = True
        if settings[key] in ['False', 'false', 'No', 'no'] and settings[key] != 0:
            settings[key] = False

    # GET ARGS to populate fields
    # Project & Item
    proj_slug = request.args.get('proj')
    item_id = request.args.get('item')
    project_list = Category.query.all()
    item = ''
    project = ''
    files = ''
    run_param = ['runname', 'description', 'seq_type', 'fastq1', 'fastq2']
    pre_param = ['preprocess', 'trim_quality', 'avg_qual_cutoff', 'min_read_len', 'n_base_cutoff', 'low_comp_filter',
                 'trim_polya', 'cut_5_prime', 'cut_3_prime']
    pangia_param = ['seed_length', 'min_align_score', 'score_method', 'min_score', 'min_read_count', 'min_read_rsnb',
                    'min_linear_len', 'min_genome_cov', 'min_depth', 'min_rs_depth', 'pathogen_discovery',
                    'display_all']
                    #'run_annoy', 'run_tmark', 'run_dt']

    db_fastas = []
    # Get all of the .fa and .fasta files in the database
    for file in os.scandir(settings['pangia_db']):
        ext = str(file.name).split('.')[-1]
        if ext in ['fa', 'fasta']:
            db_fastas.append(file.name)

    db_fastas = sorted(db_fastas)

    # Check if project is valid and get info
    if proj_slug and proj_slug != '':
        check_project = Category.query.filter_by(slug=proj_slug).count()
        if check_project > 0:
            project = Category.query.filter_by(slug=proj_slug).first()
            files = Item.query.filter_by(category_id=project.id).all()

        # Item
        if item_id and item_id != '':
            check_item = Item.query.filter_by(id=item_id, category_id=project.id).count()
            if check_item > 0:
                item = Item.query.filter_by(id=item_id, category_id=project.id).first()

        # Start form and set defaults
        form = StartPanGIARun(fastq1='fastq_{}'.format(item_id))
        form.get_fastq_choices(project.id)

        # Form submit and validation
        if form.submit.data:
            if form.validate_on_submit():
                print('valid')
                # Form is valid - redirect to the pangia action script to start the background job
                return redirect(url_for('main.action_pangia'), code=307)

        form.set_values(settings)

        all_param = run_param + pre_param + pangia_param
        errors = set()
        # Set the class for the fields based on their type and if there are errors
        for key in all_param:
            if form[key].type == 'BooleanField':
                if form[key].errors:
                    form[key].render_kw = {'class': 'form-check-input is-invalid', 'style': 'margin-left:0;'}
                    errors.add('{}<br>'.format(form[key].errors[0]))
                else:
                    form[key].render_kw = {'class': 'form-check-input', 'style': 'margin-left:0;'}
            else:
                if form[key].errors:
                    form[key].render_kw = {'class': 'form-control is-invalid'}
                    errors.add('{}<br>'.format(form[key].errors[0]))
                else:
                    form[key].render_kw = {'class': 'form-control'}

        # Flash errors to the user
        if len(errors) != 0:
            flash(Markup(''.join(errors)), 'warning')

    return render_template('pangia/run_pangia.html', title="Run PanGIA", project_list=project_list, project=project,
                           files=files, item=item, run_param=run_param, pre_param=pre_param, pangia_param=pangia_param,
                           db_fastas=db_fastas, form=form)


@bp.route('/action_pangia', methods=['POST'])
def action_pangia():
    # Format variables for pangia run
    if request.form.get('fastq1') != '' and request.form.get('fastq2') != '':
        i1 = Item.query.get(int(request.form.get('fastq1').replace('fastq_', '')))
        i2 = Item.query.get(int(request.form.get('fastq2').replace('fastq_', '')))
        fastq_loc = '{} {}'.format(i1.item_path, i2.item_path)
        items_run = [i1.id, i2.id]
    else:
        i1 = Item.query.get(int(request.form.get('fastq1').replace('fastq_', '')))
        fastq_loc = '{}'.format(i1.item_path)
        items_run = [i1.id]

    # Set up a dictionary of varibles for the pangia run
    pangia_settings = {
        'pangia_loc': settings['pangia_dir'],
        'pangia_db': settings['pangia_db'],
        'fastq_loc': fastq_loc,
        'threads': settings['threads'],
        'tmp_dir': '{}{}/results/tmp'.format(settings['upload_dir'], request.form.get('proj_slug')),
        'items_run': items_run,
        'file_stem': Path(i1.item_path).stem
    }

    run_param = ['runname', 'description', 'seq_type', 'fastq1', 'fastq2']
    pre_param = ['preprocess', 'trim_quality', 'avg_qual_cutoff', 'min_read_len', 'n_base_cutoff', 'low_comp_filter',
                 'trim_polya', 'cut_5_prime', 'cut_3_prime']
    pangia_param = ['seed_length', 'min_align_score', 'score_method', 'min_score', 'min_read_count', 'min_read_rsnb',
                    'min_linear_len', 'min_genome_cov', 'min_depth', 'min_rs_depth', 'pathogen_discovery',
                    'display_all']
                    #'run_annoy', 'run_tmark', 'run_dt']

    # Add Pangia Parameters to the run settings
    for x in run_param + pre_param + pangia_param:
        pangia_settings.update({x: request.form.get(x)})

    current_user.launch_task('run_pangia', '{}'.format(request.form.get('description')), pangia_settings)
    db.session.commit()

    flash(Markup('Started a new PanGIA run for {}. See progress on <a href="{}">PanGIA results</a> page.'.format(
        Path(i1.item_path).name, url_for('main.pangia'))), 'success')
    sleep = time.sleep(3)
    return redirect(url_for('main.project_page', proj_slug=request.form.get('proj_slug')))


# ----------------------------------------------------------------------------------------------------------------------
# REAL TIME
# ----------------------------------------------------------------------------------------------------------------------
@bp.route('/real_time_pangia', methods=['GET', 'POST'])
def real_time():
    global settings
    global settings_file

    for key in settings:
        if settings[key] in ['True', 'true', 'Yes', 'yes'] and settings[key] != 1:
            settings[key] = True
        if settings[key] in ['False', 'false', 'No', 'no'] and settings[key] != 0:
            settings[key] = False

    # GET ARGS to populate fields
    run_param = ['runname', 'description', 'fastq_dir', 'project']
    # pre_param = ['preprocess', 'trim_quality', 'avg_qual_cutoff', 'min_read_len', 'n_base_cutoff', 'low_comp_filter',
    #             'trim_polya', 'cut_5_prime', 'cut_3_prime']
    # pangia_param = ['seed_length', 'min_align_score', 'score_method', 'min_score', 'min_read_count', 'min_read_rsnb',
    #                'min_linear_len', 'min_genome_cov', 'min_depth', 'min_rs_depth', 'pathogen_discovery', 'run_annoy',
    #                'run_tmark', 'run_dt']

    # Start form and set defaults
    form = StartRealTime()
    form.project_choices()

    # Form submit and validation
    if form.submit.data:
        if form.validate_on_submit():
            print('valid')
            # Form is valid - redirect to the pangia action script to start the background job
            return redirect(url_for('main.action_realtime'), code=307)

    # form.set_values(settings)

    all_param = run_param  # + pre_param + pangia_param
    errors = set()
    # Set the class for the fields based on their type and if there are errors
    for key in all_param:
        if form[key].type == 'BooleanField':
            if form[key].errors:
                form[key].render_kw = {'class': 'form-check-input is-invalid', 'style': 'margin-left:0;'}
                errors.add('{}<br>'.format(form[key].errors[0]))
            else:
                form[key].render_kw = {'class': 'form-check-input', 'style': 'margin-left:0;'}
        else:
            if form[key].errors:
                form[key].render_kw = {'class': 'form-control is-invalid'}
                errors.add('{}<br>'.format(form[key].errors[0]))
            else:
                form[key].render_kw = {'class': 'form-control'}

    # Flash errors to the user
    if len(errors) != 0:
        flash(Markup(''.join(errors)), 'warning')

    return render_template('pangia/real_time.html', title="Run Real Time PanGIA", run_param=run_param, form=form)


@bp.route('/action_realtime', methods=['POST'])
def action_realtime():
    # Set up a dictionary of varibles for the pangia run
    pangia_settings = {
        'pangia_loc': settings['pangia_dir'],
        'pangia_db': settings['pangia_db'],
        'threads': settings['threads'],
        'upload_dir': settings['upload_dir'],
        'fileloc': '{}{}/'.format(settings['upload_dir'], request.form.get('proj_slug'),'/')
    }

    run_param = ['runname', 'description', 'fastq_dir', 'project']
    pre_param = ['preprocess', 'trim_quality', 'avg_qual_cutoff', 'min_read_len', 'n_base_cutoff', 'low_comp_filter',
                 'trim_polya', 'cut_5_prime', 'cut_3_prime']
    pangia_param = ['seed_length', 'min_align_score', 'score_method', 'min_score', 'min_read_count', 'min_read_rsnb',
                    'min_linear_len', 'min_genome_cov', 'min_depth', 'min_rs_depth', 'pathogen_discovery']
                    #'run_annoy', 'run_tmark', 'run_dt']

    # Add Pangia Parameters to the run settings
    for x in run_param + pre_param + pangia_param:
        pangia_settings.update({x: request.form.get(x)})

    current_user.launch_task('run_real_time', '{}'.format(request.form.get('description')), pangia_settings)
    db.session.commit()

    #flash(Markup('Started a new PanGIA run for {}. See progress on <a href="{}">PanGIA results</a> page.'.format(Path(i1.item_path).name, url_for('main.pangia'))), 'success')
    sleep = time.sleep(3)
    return redirect(url_for('main.pangia'))


# ----------------------------------------------------------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------------------------------------------------------
@bp.route('/settings', methods=['GET', 'POST'])
@bp.route('/settings/general', methods=['GET', 'POST'])
@login_required
def settings_page():
    if 'Admin' not in current_user.get_roles():
        return redirect(url_for('main.index'))

    global settings
    global settings_file

    for key in settings:
        if settings[key] in ['True', 'true', 'Yes', 'yes'] and settings[key] != 1:
            settings[key] = True
        if settings[key] in ['False', 'false', 'No', 'no'] and settings[key] != 0:
            settings[key] = False

    form = ChangePanGIASettings()

    # Post submit for changing pangia settings
    if form.submit.data:
        new_settings = {}
        for key in settings:
            if key in ['pangia_dir', 'pangia_db', 'upload_dir'] and form[key].data[-1] != '/':
                form[key].data = '{}/'.format(form[key].data)
            new_settings.update({key: form[key].data})
        settings = new_settings
        if form.validate_on_submit():
            new_df = pd.DataFrame({'Field': list(settings.keys()), 'Value': list(settings.values())})
            new_df.to_csv(settings_file, sep=',', index=False)
            flash('Updated settings for the PanGIA application.', 'success')

    form.set_values(settings)

    errors = set()
    # Set the class for the fields based on their type and if there are errors
    for key in settings:
        if form[key].type == 'BooleanField':
            if form[key].errors:
                form[key].render_kw = {'class': 'form-check-input is-invalid', 'style': 'margin-left:0;'}
                errors.add('{}<br>'.format(form[key].errors[0]))
            else:
                form[key].render_kw = {'class': 'form-check-input', 'style': 'margin-left:0;'}
        else:
            if form[key].errors:
                form[key].render_kw = {'class': 'form-control is-invalid'}
                errors.add('{}<br>'.format(form[key].errors[0]))
            else:
                form[key].render_kw = {'class': 'form-control'}

    # Flash errors to the user
    if len(errors) != 0:
        flash(Markup(''.join(errors)), 'warning')

    # Make a few lists to make it easier to group in html
    system_param = ['pangia_dir', 'pangia_db', 'upload_dir', 'threads']
    pre_param = ['preprocess', 'trim_quality', 'avg_qual_cutoff', 'min_read_len', 'n_base_cutoff', 'low_comp_filter',
                 'trim_polya', 'cut_5_prime', 'cut_3_prime']
    pangia_param = ['seed_length', 'min_align_score', 'score_method', 'min_score', 'min_read_count', 'min_read_rsnb',
                    'min_linear_len', 'min_genome_cov', 'min_depth', 'min_rs_depth', 'pathogen_discovery',
                    'display_all']
                    #'run_annoy', 'run_tmark', 'run_dt']

    return render_template('admin/settings.html', title='General', form=form, system_param=system_param,
                           pre_param=pre_param, pangia_param=pangia_param)


@bp.route('/settings/projects', methods=['GET', 'POST'])
@login_required
def settings_projects():
    if 'Admin' not in current_user.get_roles():
        return redirect(url_for('main.index'))

    form = AddCategoryForm(prefix='form')

    if form.submit.data:
        if form.validate_on_submit():
            # <------- Need to make these names safe
            new_cat = Category(name=form.name.data, description=form.description.data, slug=form.slug.data,
                               parent_id=form.parent_id.data, order=form.order.data)
            db.session.add(new_cat)
            db.session.commit()
            flash('Successfully added a new Project: {}'.format(form.name.data), 'success')

    categories = Category.query.all()
    return render_template('admin/settings.html', title='Projects', categories=categories, form=form)


@bp.route('/settings/templates', methods=['GET', 'POST'])
@login_required
def settings_templates():
    if 'Admin' not in current_user.get_roles():
        return redirect(url_for('main.index'))

    form = AddFileTemplate(prefix='form')
    form.metatypes.choices = form.get_metatypes()

    if form.submit.data:
        if form.validate_on_submit():
            new_template = MetaTemplate(name=form.name.data, description=form.description.data,
                                        file_ext=form.file_ext.data)
            db.session.add(new_template)
            db.session.flush()
            for x in form.metatypes.data:
                x = int(x)
                add_metatype = MetaTypeToTemplates(template_id=new_template.id, metatype_id=x, order=0, size=0)
                db.session.add(add_metatype)
            db.session.commit()

    meta_temp = MetaTemplate.query.all()
    return render_template('admin/settings.html', title='File-Templates', meta_temp=meta_temp, form=form)


@bp.route('/settings/meta-types', methods=['GET', 'POST'])
@login_required
def settings_meta_types():
    if 'Admin' not in current_user.get_roles():
        return redirect(url_for('main.index'))

    form = AddMetaType(prefix='form')

    if form.submit.data:
        if form.validate_on_submit():
            if form.value_type.data == 'choice':
                choices = form.choices.data
            else:
                choices = ''
            new_metatype = MetaType(name=form.name.data, description=form.description.data, choices=choices,
                                    value_type=form.value_type.data, is_required=form.is_required.data)
            db.session.add(new_metatype)
            db.session.commit()
            flash('Successfully added meta type - {}'.format(form.name.data), 'success')

    meta_type = MetaType.query.all()
    return render_template('admin/settings.html', title='Meta-Types', meta_type=meta_type, form=form)


# ----------------------------------------------------------------------------------------------------------------------
# USER PAGES
# ----------------------------------------------------------------------------------------------------------------------
@bp.route('/users', methods=['GET', 'POST'])
@login_required
def viewusers():
    if 'Admin' not in current_user.get_roles():
        return redirect(url_for('main.index'))

    form1 = AddUserForm(prefix='form1')
    # form2 = AddRoleForm(prefix='form2')
    # FORM 1 SUBMIT - Add new user
    if form1.submit.data:
        if form1.validate_on_submit():
            new_user = User(fname=form1.fname.data, lname=form1.lname.data, email=form1.email.data,
                            username=form1.username.data)
            new_user.set_password(form1.password.data)
            db.session.add(new_user)
            db.session.commit()
            flash('Successfully added {} {}'.format(form1.fname.data, form1.lname.data), 'success')

    users = User.query.all()

    return render_template('admin/user.html', title='Manage Users', users=users, form1=form1)  # , form2=form2)


# Delete User ----------------------------------------------------------------------------------------------------------
@bp.route('/users/delete-user', methods=['GET', 'POST'])
@login_required
def delete_user():
    stuff = 'stuff'
