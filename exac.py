#!/usr/bin/env python2

import itertools
import json
import os
import pymongo
import pysam
import gzip
from parsing import *
import lookups
import random
from utils import *
from pycoverage import *
import auth

from flask import Flask, Response, request, session, g, redirect, url_for, abort, render_template, flash, jsonify
from flask_compress import Compress
from flask_errormail import mail_on_500
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from collections import defaultdict, Counter

from multiprocessing import Process
import multiprocessing
import glob
import traceback
import time
import sys
import functools
import contextlib

app = Flask(__name__)
app.config.from_object('flask_config.BravoTestConfig')
mail_on_500(app, app.config['ADMINS'])
Compress(app)

REGION_LIMIT = int(1e5)
EXON_PADDING = 50

def get_db(new_connection=False):
    # Only use the database within a request context! Something about threads/forks.
    # See <https://jira.mongodb.org/browse/PYTHON-961>
    # Note: I just added `connect=False`, so maybe we don't need this function anymore (unless used with new_connection=True)
    if new_connection:
        client = pymongo.MongoClient(host=app.config['MONGO']['host'], port=app.config['MONGO']['port'], connect=False)
    else:
        client = get_db._mongo_client
    return client[app.config['MONGO']['name']]
get_db._mongo_client = pymongo.MongoClient(host=app.config['MONGO']['host'], port=app.config['MONGO']['port'], connect=False)

def get_autocomplete_strings():
    if not hasattr(get_autocomplete_strings, '_cache'):
        autocomplete_strings = get_db().genes.distinct('gene_name')
        autocomplete_strings.extend(get_db().genes.distinct('other_names', {'other_names': {'$ne': None}}))
        get_autocomplete_strings._cache = sorted(set(autocomplete_strings))
    return get_autocomplete_strings._cache

def get_coverages():
    if not hasattr(get_coverages, '_cache'):
        coverages = CoverageCollection()
        for coverage in app.config['BASE_COVERAGE']:
            coverages.setTabixPath(coverage['min-length-bp'], coverage['max-length-bp'], coverage['chrom'], coverage['path'])
        coverages.openAll()
        get_coverages._cache = coverages
    return get_coverages._cache


def get_tabix_file_contig_pairs(tabix_filenames):
    def _convert_contig_to_int(contig):
        try: return int(contig)
        except: return 0 # parse X/Y right at the beginning.
    for tabix_filename in tabix_filenames:
        with pysam.Tabixfile(tabix_filename) as tabix_file:
            for contig in sorted(tabix_file.contigs, key=_convert_contig_to_int): # Hopefully going from large -> small chroms keeps load higher.
                yield (tabix_filename, contig)

def get_records_from_tabix_contig(tabix_filename, contig, record_parser):
    start_time = time.time()
    with pysam.Tabixfile(tabix_filename) as tabix_file:
        record_i = 0 # in case record_parser never yields anything.
        for record_i, parsed_record in enumerate(record_parser(itertools.chain(tabix_file.header, tabix_file.fetch(contig, 0, 10**10, multiple_iterators=True))), start=1):
            yield parsed_record

            if record_i % int(1e6) == 0:
                print("Loaded {:11,} records in {:6,} seconds from contig {!r:6} of {!r}".format(record_i, int(time.time()-start_time), contig, tabix_filename))
    print("Loaded {:11,} records in {:6,} seconds from contig {!r:6} of {!r}".format(record_i, int(time.time()-start_time), contig, tabix_filename))


def _load_variants_from_tabix_file_and_contig(args):
    tabix_file, contig = args
    db = get_db(new_connection=True)
    variants_generator = get_records_from_tabix_contig(tabix_file, contig, get_variants_from_sites_vcf)
    try:
        db.variants.insert(variants_generator, w=0)
    except pymongo.errors.InvalidOperation:
        pass  # handle error when variant_generator is empty

def load_variants_file():
    db = get_db()
    db.variants.drop()
    print("Dropped db.variants")

    db.variants.ensure_index('xpos')
    db.variants.ensure_index('xstart')
    db.variants.ensure_index('xstop')
    db.variants.ensure_index('rsids')
    db.variants.ensure_index('genes')
    db.variants.ensure_index('transcripts')

    if len(app.config['SITES_VCFS']) == 0:
        raise IOError("No vcf file found")

    with contextlib.closing(multiprocessing.Pool(app.config['LOAD_DB_PARALLEL_PROCESSES'])) as pool:
        # workaround for Pool.map() from <http://stackoverflow.com/a/1408476/1166306>
        pool.map_async(_load_variants_from_tabix_file_and_contig, get_tabix_file_contig_pairs(app.config['SITES_VCFS'])).get(9999999)


def load_gene_models():
    db = get_db()

    db.genes.drop()
    db.transcripts.drop()
    db.exons.drop()
    print 'Dropped db.genes, db.transcripts, and db.exons.'

    start_time = time.time()

    canonical_transcripts = {}
    with gzip.open(app.config['CANONICAL_TRANSCRIPT_FILE']) as canonical_transcript_file:
        for gene, transcript in get_canonical_transcripts(canonical_transcript_file):
            canonical_transcripts[gene] = transcript

    omim_annotations = {}
    with gzip.open(app.config['OMIM_FILE']) as omim_file:
        for fields in get_omim_associations(omim_file):
            if fields is None:
                continue
            gene, transcript, accession, description = fields
            omim_annotations[gene] = (accession, description)

    dbnsfp_info = {}
    with gzip.open(app.config['DBNSFP_FILE']) as dbnsfp_file:
        for dbnsfp_gene in get_dbnsfp_info(dbnsfp_file):
            other_names = [other_name.upper() for other_name in dbnsfp_gene['gene_other_names']]
            dbnsfp_info[dbnsfp_gene['ensembl_gene']] = (dbnsfp_gene['gene_full_name'], other_names)

    print 'Done loading metadata. Took %s seconds' % int(time.time() - start_time)

    # grab genes from GTF
    start_time = time.time()
    with gzip.open(app.config['GENCODE_GTF']) as gtf_file:
        for gene in get_genes_from_gencode_gtf(gtf_file):
            gene_id = gene['gene_id']
            if gene_id in canonical_transcripts:
                gene['canonical_transcript'] = canonical_transcripts[gene_id]
            if gene_id in omim_annotations:
                gene['omim_accession'] = omim_annotations[gene_id][0]
                gene['omim_description'] = omim_annotations[gene_id][1]
            if gene_id in dbnsfp_info:
                gene['full_gene_name'] = dbnsfp_info[gene_id][0]
                gene['other_names'] = dbnsfp_info[gene_id][1]
            db.genes.insert(gene, w=0)

    print 'Done loading genes. Took %s seconds' % int(time.time() - start_time)

    start_time = time.time()
    db.genes.ensure_index('gene_id')
    db.genes.ensure_index('gene_name_upper')
    db.genes.ensure_index('gene_name')
    db.genes.ensure_index('other_names')
    db.genes.ensure_index('xstart')
    db.genes.ensure_index('xstop')
    print 'Done indexing gene table. Took %s seconds' % int(time.time() - start_time)

    # and now transcripts
    start_time = time.time()
    with gzip.open(app.config['GENCODE_GTF']) as gtf_file:
        db.transcripts.insert((transcript for transcript in get_transcripts_from_gencode_gtf(gtf_file)), w=0)
    print 'Done loading transcripts. Took %s seconds' % int(time.time() - start_time)

    start_time = time.time()
    db.transcripts.ensure_index('transcript_id')
    db.transcripts.ensure_index('gene_id')
    print 'Done indexing transcript table. Took %s seconds' % int(time.time() - start_time)

    # Building up gene definitions
    start_time = time.time()
    with gzip.open(app.config['GENCODE_GTF']) as gtf_file:
        db.exons.insert((exon for exon in get_exons_from_gencode_gtf(gtf_file)), w=0)
    print 'Done loading exons. Took %s seconds' % int(time.time() - start_time)

    start_time = time.time()
    db.exons.ensure_index('exon_id')
    db.exons.ensure_index('transcript_id')
    db.exons.ensure_index('gene_id')
    print 'Done indexing exon table. Took %s seconds' % int(time.time() - start_time)


def _load_dbsnp_from_tabix_file_and_contig(args):
    dbsnp_file, contig = args
    db = get_db(new_connection=True)
    dbsnp_record_generator = get_records_from_tabix_contig(dbsnp_file, contig, get_snp_from_dbsnp_file)
    try:
        db.dbsnp.insert(dbsnp_record_generator, w=0)
    except pymongo.errors.InvalidOperation:
        pass  # handle error when coverage_generator is empty

def load_dbsnp_file():
    db = get_db()

    db.dbsnp.drop()
    db.dbsnp.ensure_index('rsid') # It seems faster to build these indexes before inserts.  Strange.
    db.dbsnp.ensure_index('xpos')
    start_time = time.time()
    dbsnp_file = app.config['DBSNP_FILE']

    print "Loading dbsnp from %s" % dbsnp_file
    if os.path.isfile(dbsnp_file + ".tbi"):
        with contextlib.closing(multiprocessing.Pool(app.config['LOAD_DB_PARALLEL_PROCESSES'])) as pool:
            # workaround for Pool.map() from <http://stackoverflow.com/a/1408476/1166306>
            pool.map_async(_load_dbsnp_from_tabix_file_and_contig, get_tabix_file_contig_pairs([dbsnp_file])).get(9999999)
        print('Done loading dbSNP in {:,} seconds'.format(int(time.time() - start_time)))

    elif os.path.isfile(dbsnp_file):
        # see if non-tabixed .gz version exists
        print(("WARNING: %(dbsnp_file)s.tbi index file not found. Will use single thread to load dbsnp."
               "To create a tabix-indexed dbsnp file based on UCSC dbsnp, do: \n"
               "   wget http://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/snp141.txt.gz \n"
               "   gzcat snp141.txt.gz | cut -f 1-5 | bgzip -c > snp141.txt.bgz \n"
               "   tabix -0 -s 2 -b 3 -e 4 snp141.txt.bgz") % locals())
        with gzip.open(dbsnp_file) as f:
            db.dbsnp.insert((snp for snp in get_snp_from_dbsnp_file(f)), w=0)

    else:
        raise Exception("dbsnp file %s(dbsnp_file)s not found." % locals())


def precalculate_whether_variant_is_ever_missense_or_lof():
    missense_and_lof_csqs = csq_order[:csq_order.index('MISSENSE_THRESHOLD')]
    missense_and_lof_csqs.remove('LOF_THRESHOLD')
    regex = r'(^|&)({})(&|$)'.format('|'.join(missense_and_lof_csqs))
    db = get_db()
    print('Updating all {:,} variants for all {} missense/LoF consequences...'.format(db.variants.count(), len(missense_and_lof_csqs)))
    start_time = time.time()
    result = db.variants.update_many(
        {'vep_annotations.Consequence': {'$regex': regex}},
        {'$set': {'sometimes_missense_or_lof': 1}}
    )
    print "updated {:,} documents in {:,.0f} seconds".format(result.matched_count, time.time() - start_time)


def precalculate_metrics():
    import numpy
    db = get_db()
    print 'Reading %s variants...' % db.variants.count()
    # For some reason using Counter() gives this linear performance, whereas it was slowing down 10X towards the end of 150M variants with just list.append().
    metrics_to_use_with_counter = {'DP', 'site_quality'}
    metrics = defaultdict_that_passes_key_to_default_factory(lambda key: Counter() if key in metrics_to_use_with_counter else list())
    qualities_by_af = defaultdict(Counter)
    start_time = time.time()
    for variant_i, variant in enumerate(db.variants.find(projection=['quality_metrics', 'site_quality', 'allele_num', 'allele_count'])):
        if 'DP' in variant['quality_metrics'] and float(variant['quality_metrics']['DP']) == 0:
            print('Warning: variant with id {} has depth of 0'.format(variant['_id']))
        for metric, value in variant['quality_metrics'].iteritems():
            if metric in metrics_to_use_with_counter:
                metrics[metric][float(value)] += 1
            else:
                metrics[metric].append(float(value))
        qual = float(variant['site_quality'])
        metrics['site_quality'][qual] += 1
        if variant['allele_num'] == 0: continue
        if variant['allele_count'] == 1:
            qualities_by_af['singleton'][qual] += 1
        elif variant['allele_count'] == 2:
            qualities_by_af['doubleton'][qual] += 1
        else:
            variant_af = float(variant['allele_count'])/variant['allele_num']
            for bucket_af in AF_BUCKETS:
                if variant_af < bucket_af:
                    qualities_by_af[bucket_af][qual] += 1
                    break
        if variant_i % int(1e6) == 0:
            print 'Read %s variants. Took %s seconds' % (variant_i, int(time.time() - start_time))
    print 'Done reading variants. Dropping metrics database... '
    db.metrics.drop()
    print 'Dropped metrics database. Calculating metrics...'
    for metric in metrics:
        bin_range = None
        data = metrics[metric]
        if metric in metrics_to_use_with_counter:
            data = list(data.elements())
        if metric == 'DP':
            data = map(numpy.log, data)
        if metric == 'FS':
            bin_range = (0, 20)
        elif metric == 'VQSLOD':
            bin_range = (-20, 20)
        elif metric == 'InbreedingCoeff':
            bin_range = (0, 1)
        if bin_range is not None:
            data = [x if (x > bin_range[0]) else bin_range[0] for x in data]
            data = [x if (x < bin_range[1]) else bin_range[1] for x in data]
        hist = numpy.histogram(data, bins=40, range=bin_range)
        edges = hist[1]
        # mids = [(edges[i]+edges[i+1])/2 for i in range(len(edges)-1)]
        lefts = [edges[i] for i in range(len(edges)-1)]
        db.metrics.insert({
            'metric': metric,
            'mids': lefts,
            'hist': hist[0].tolist()
        })
    for af_bin in qualities_by_af:
        qualities_as_list = qualities_by_af[af_bin].elements()
        hist = numpy.histogram(map(numpy.log, qualities_as_list), bins=40)
        edges = hist[1]
        mids = [(edges[i]+edges[i+1])/2 for i in range(len(edges)-1)]
        db.metrics.insert({
            'metric': 'binned_%s' % af_bin,
            'mids': mids,
            'hist': hist[0].tolist()
        })
    db.metrics.ensure_index('metric')
    print 'Done pre-calculating metrics!'

def create_users():
    db = get_db()
    db.users.drop()
    print 'Dropped users database.'
    db.users.ensure_index('user_id')
    print 'Created new users database.'


def require_agreement_to_terms_and_store_destination(func):
    """
    This decorator for routes checks that the user is logged in and has agreed to the terms.
    If they haven't, their intended destination is stored and they're sent to get authorized.
    I think that it has to be placed AFTER @app.route() so that it can capture `request.path`.
    """
    # inspired by <https://flask-login.readthedocs.org/en/latest/_modules/flask_login.html#login_required>
    @functools.wraps(func)
    def decorated_view(*args, **kwargs):
        if hasattr(current_user, 'agreed_to_terms') and current_user.agreed_to_terms:
            return func(*args, **kwargs)
        else:
            print('unauthorized user {!r} visited the url [{!r}]'.format(current_user, request.path))
            session['original_destination'] = request.path
            return redirect(url_for('get_authorized'))
        return func(*args, **kwargs)
    return decorated_view


@app.route('/')
def homepage():
    return render_template('homepage.html')


@app.route('/api/autocomplete')
def autocomplete():
    query = request.args.get('query', '')
    suggestions = lookups.get_awesomebar_suggestions(get_autocomplete_strings(), query)
    return jsonify([{'value': s} for s in sorted(suggestions)])


@app.route('/awesome')
def awesome():
    db = get_db()
    query = request.args.get('query')
    datatype, identifier = lookups.get_awesomebar_result(db, query)

    print "Searched for %s: %s" % (datatype, identifier)
    if datatype == 'gene':
        return redirect('/gene/{}'.format(identifier))
    elif datatype == 'transcript':
        return redirect('/transcript/{}'.format(identifier))
    elif datatype == 'variant':
        return redirect('/variant/{}'.format(identifier))
    elif datatype == 'region':
        return redirect('/region/{}'.format(identifier))
    elif datatype == 'dbsnp_variant_set':
        return redirect('/dbsnp/{}'.format(identifier))
    elif datatype == 'not_found':
        return redirect('/not_found/{}'.format(identifier))
    else:
        raise Exception


@app.route('/variant/<variant_str>')
@require_agreement_to_terms_and_store_destination
def variant_page(variant_str):
    db = get_db()
    try:
        variant = lookups.get_variant_by_variant_id(db, variant_str, default_to_boring_variant=True)

        consequences = get_consequences_drilldown_for_variant(variant)
        gene_for_top_csq, top_HGVSs = get_top_gene_and_top_hgvss_for_consequences_drilldown(consequences)
        consequence_columns = split_consequence_drilldown_into_two_columns(consequences)

        base_coverage = lookups.get_coverage_for_bases(get_coverages(), variant['xpos'], variant['xpos'] + len(variant['ref']) - 1)
        metrics = lookups.get_metrics(db, variant)

        pop_afs = get_pop_afs(variant)
        if pop_afs:
            variant['pop_afs'] = pop_afs
            variant['pop_afs'][app.config['DATASET_NAME']] = variant['allele_freq']

        lookups.remove_some_extraneous_information(variant)

        print 'Rendering variant: %s' % variant_str
        return render_template(
            'variant.html',
            variant=variant,
            base_coverage=base_coverage,
            consequences=consequences,
            consequence_columns=consequence_columns,
            any_covered=bool(base_coverage),
            metrics=metrics,
            top_HGVSs=top_HGVSs,
            gene_for_top_csq=gene_for_top_csq,
        )
    except Exception, e:
        print 'Failed on variant:', variant_str, '; Error=', traceback.format_exc()
        abort(404)


@app.route('/gene/<gene_id>')
@require_agreement_to_terms_and_store_destination
def gene_page(gene_id):
    db = get_db()
    try:
        gene = lookups.get_gene(db, gene_id)
        if gene is None:
            abort(404)
        allowed_chroms = [str(chrom) for chrom in range(1,1+22)] + ['X']
        if gene['chrom'] not in allowed_chroms:
            return error_page("Sorry, {} doesn't currently contain chromosome {}".format(
                app.config['DATASET_NAME'], gene['chrom']))
        print 'Rendering gene: %s' % gene_id
        variants_in_gene = lookups.get_most_important_variants_in_gene(db, gene_id)
        num_variants_in_gene = lookups.get_num_variants_in_gene(db, gene_id)
        transcripts_in_gene = lookups.get_transcripts_in_gene(db, gene_id)

        exons_and_utrs = lookups.get_exons_in_gene(db, gene_id)

        coverage_stats = lookups.get_coverage_for_bases(get_coverages(), gene['xstart'] - EXON_PADDING, gene['xstop'] + EXON_PADDING)

        return render_template(
            'gene.html',
            gene=gene,
            exons_and_utrs=exons_and_utrs,
            variants_in_gene=variants_in_gene,
            num_variants_in_gene=num_variants_in_gene,
            transcripts_in_gene=transcripts_in_gene,
            coverage_stats=coverage_stats,
            csq_order=csq_order,
        )
    except Exception, e:
        print 'Failed on gene:', gene_id, ';Error=', traceback.format_exc()
        abort(404)


@app.route('/transcript/<transcript_id>')
@require_agreement_to_terms_and_store_destination
def transcript_page(transcript_id):
    db = get_db()
    try:
        transcript = lookups.get_transcript(db, transcript_id)

        print 'Rendering transcript: %s' % transcript_id

        gene = lookups.get_gene(db, transcript['gene_id'])
        gene['transcripts'] = lookups.get_transcripts_in_gene(db, transcript['gene_id'])
        variants_in_transcript = lookups.get_most_important_variants_in_transcript(db, transcript_id)
        coverage_stats = lookups.get_coverage_for_bases(get_coverages(), transcript['xstart'] - EXON_PADDING, transcript['xstop'] + EXON_PADDING)
        num_variants_in_transcript = lookups.get_num_variants_in_transcript(db, transcript_id)

        return render_template(
            'transcript.html',
            transcript=transcript,
            variants_in_transcript=variants_in_transcript,
            num_variants_in_transcript=num_variants_in_transcript,
            coverage_stats=coverage_stats,
            gene=gene,
            csq_order=csq_order,
        )
    except Exception, e:
        print 'Failed on transcript:', transcript_id, ';Error=', traceback.format_exc()
        abort(404)

@app.route('/api/variants_in_gene/<gene_id>')
@require_agreement_to_terms_and_store_destination
def variants_gene_api(gene_id):
    db = get_db()
    try:
        variants_in_gene = lookups.get_variants_in_gene(db, gene_id)
        return jsonify(variants_in_gene)
    except Exception as e:
        print 'Failed on gene:', gene_id, ';Error=', traceback.format_exc()
        abort(404)

@app.route('/api/variants_in_transcript/<transcript_id>')
@require_agreement_to_terms_and_store_destination
def variants_transcript_api(transcript_id):
    db = get_db()
    try:
        variants_in_transcript = lookups.get_variants_in_transcript(db, transcript_id)
        return jsonify(variants_in_transcript)
    except Exception as e:
        print 'Failed on transcript:', transcript_id, ';Error=', traceback.format_exc()
        abort(404)

@app.route('/api/variants_in_region/<region_id>')
@require_agreement_to_terms_and_store_destination
def variants_region_api(region_id):
    db = get_db()
    try:
        chrom, start, stop = region_id.split('-')
        start, stop = int(start), int(stop)
        variants_in_region = lookups.get_variants_in_region(db, chrom, start, stop)
        return jsonify(variants_in_region)
    except Exception as e:
        print 'Failed on region:', region_id, ';Error=', traceback.format_exc()
        abort(404)

@app.route('/api/coverage/region/<region_id>')
@require_agreement_to_terms_and_store_destination
def region_coverage_api(region_id):
    db = get_db()
    try:
        chrom, start, stop = region_id.split('-')
        start, stop = int(start), int(stop)
        xstart, xstop = get_xpos(chrom, start), get_xpos(chrom, stop)
        coverage_stats = lookups.get_coverage_for_bases(get_coverages(), xstart, xstop)
        return jsonify(coverage_stats)
    except Exception as e:
        print 'Failed on region:', region_id, ';Error=', traceback.format_exc()
        abort(404)

@app.route('/region/<region_id>')
@require_agreement_to_terms_and_store_destination
def region_page(region_id):
    db = get_db()
    try:
        region = region_id.split('-')
        print 'Rendering region: %s' % region_id

        if len(region) != 3:
            return error_page("Sorry, '{}' doesn't look like a valid region. A valid region looks like 1-55530545-55531525.".format(region_id))

        chrom, start, stop = region[0], int(region[1]), int(region[2])
        if stop - start > REGION_LIMIT:
            return error_page("The region you requested, '{}', is {:,} bases long.  We only accept regions shorter than {:,} bases.".format(region_id, stop - start, REGION_LIMIT))
        if stop < start:
            return error_page("The region you requested, '{}', stops before it starts.  Did you mean '{chrom}-{stop}-{start}'?".format(region_id, chrom=chrom, start=start, stop=stop))
        if start == stop:
            start -= 20
            stop += 20

        genes_in_region = lookups.get_genes_in_region(db, chrom, start, stop)
        variants_in_region = lookups.get_variants_in_region(db, chrom, start, stop)
        xstart = get_xpos(chrom, start)
        xstop = get_xpos(chrom, stop)
        coverage_stats = lookups.get_coverage_for_bases(get_coverages(), xstart, xstop)
        return render_template(
            'region.html',
            genes_in_region=genes_in_region,
            variants_in_region=variants_in_region,
            chrom=chrom,
            start=start,
            stop=stop,
            coverage_stats=coverage_stats,
            csq_order=csq_order,
        )
    except Exception, e:
        print 'Failed on region:', region_id, ';Error=', traceback.format_exc()
        abort(404)


@app.route('/dbsnp/<rsid>')
@require_agreement_to_terms_and_store_destination
def dbsnp_page(rsid):
    db = get_db()
    try:
        print 'Rendering multi-variant rsid: %s' % rsid
        variants = lookups.get_variants_by_rsid(db, rsid)
        if variants is None or len(variants) == 0:
            return error_page("There are no variants with the rsid '{}'".format(rsid))
        return error_page('There are multiple variants at the location of rsid {}: {}'.format(
            rsid,
            ', '.join('{chrom}-{pos}-{ref}-{alt}'.format(**variant) for variant in variants)))
    except Exception, e:
        print 'Failed on rsid:', rsid, ';Error=', traceback.format_exc()
        abort(404)


@app.route('/not_found/<query>')
def not_found_page(query):
    return render_template(
        'not_found.html',
        query=query
    )

@app.route('/error/<message>')
@app.errorhandler(404)
def error_page(message):
    return render_template(
        'error.html',
        message=message
    ), 404

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/terms')
def terms_page():
    return render_template('terms.html')


# OAuth2
google_sign_in = auth.GoogleSignIn(app)

lm = LoginManager(app)
lm.login_view = 'homepage'

class User(UserMixin):
    "A user's id is their email address."
    def __init__(self, username=None, email=None, agreed_to_terms=False):
        self.username = username
        self.email = email
        self.agreed_to_terms = agreed_to_terms
    def get_id(self):
        return self.email
    def __repr__(self):
        return "<User email={!r} username={!r} agreed_to_terms={!r}>".format(self.email, self.username, self.agreed_to_terms)

def encode_user(user):
    return {'_type': 'User', 'user_id': user.get_id(), 'username': user.username, 'email': user.email, 'agreed_to_terms': user.agreed_to_terms}

def decode_user(document):
    assert document['_type'] == 'User'
    return User(document['username'], document['email'], document['agreed_to_terms'])

@lm.user_loader
def load_user(id):
    db = get_db()
    document = db.users.find_one({'user_id': id}, projection = {'_id': False})

    if document:
        u = decode_user(document)
        print('user [{!r}] found with id [{!r}]'.format(u, id))
    else:
        # This method is supposed to support bad `id`s.
        print('user not found with id [{!r}]'.format(id))
        u = None

    return u

@app.route('/agree_to_terms')
def agree_to_terms():
    "this route is for when the user has clicked 'I agree to the terms'."
    if not current_user.is_anonymous:
        current_user.agreed_to_terms = True
        db = get_db()
        result = db.users.update_one({"user_id": current_user.get_id()}, {"$set": {"agreed_to_terms": current_user.agreed_to_terms}})
    print('User [{!r}] agreed to the terms!'.format(current_user))
    return redirect(url_for('get_authorized'))

@app.route('/logout')
def logout():
    print('logging out user {!r}'.format(current_user))
    logout_user()
    return redirect(url_for('homepage'))

@app.route('/login_with_google')
def login_with_google():
    "this route is for the login button"
    session['original_destination'] = url_for('homepage')
    return redirect(url_for('get_authorized'))

@app.route('/get_authorized')
def get_authorized():
    "This route tries to be clever and handle lots of situations."
    if current_user.is_anonymous:
        return google_sign_in.authorize()
    elif not current_user.agreed_to_terms:
        return redirect(url_for('terms_page'))
    else:
        if 'original_destination' in session:
            orig_dest = session['original_destination']
            del session['original_destination'] # We don't want old destinations hanging around.  If this leads to problems with re-opening windows, disable this line.
        else:
            orig_dest = url_for('homepage')
        return redirect(orig_dest)

@app.route('/callback/google')
def oauth_callback_google():
    if not current_user.is_anonymous:
        return redirect(url_for('homepage'))
    try:
        username, email = google_sign_in.callback() # oauth.callback reads request.args.
    except Exception as exc:
        print('Error in google_sign_in.callback():')
        print(exc)
        print(traceback.format_exc())
        flash('Something is wrong with authentication.  Please email pjvh@umich.edu')
        return redirect(url_for('homepage'))
    if email is None:
        # I need a valid email address for my user identification
        flash('Authentication failed by failing to get an email address.  Please email pjvh@umich.edu')
        return redirect(url_for('homepage'))

    if app.config['EMAIL_WHITELIST']:
        if email.lower() not in app.config['EMAIL_WHITELIST']:
            flash('Your email, {}, is not in the list of allowed emails. If it should be, email pjvh@umich.edu to request permission.'.format(email.lower()))
            return redirect(url_for('homepage'))

    # Look if the user already exists

    db = get_db()
    document = db.users.find_one({'user_id': email}, projection = {'_id': False})

    if document:
        user = decode_user(document)
    else:
        user = User(email=email, username=username or email.split('@')[0])
        db.users.insert(encode_user(user))

    # Log in the user, by default remembering them for their next visit
    # unless they log out.
    login_user(user, remember=True)

    return redirect(url_for('get_authorized'))

@app.after_request
def apply_caching(response):
    # prevent click-jacking vulnerability identified by BITs
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0', help='the hostname to use to access this server')
    parser.add_argument('--port', type=int, default=5000, help='an integer for the accumulator')
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, threaded=True)
