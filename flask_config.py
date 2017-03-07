# Note: Flask will only copy UPPERCASE variable names from your config class into `app.config`.

import sys
import os.path
import glob
import whitelist_topmed
import whitelist_topmed_devs
import whitelist_inpsyght

class BaseConfig(object):
    DEBUG = False
    TESTING = False

    SECRET_KEY = 'development key'

    # Gotten from <https://console.developers.google.com/apis/credentials>
    # see the nice documentation at <https://support.google.com/cloud/answer/6158849?hl=en&ref_topic=6262490>
    GOOGLE_LOGIN_CLIENT_ID = 'fake key'
    GOOGLE_LOGIN_CLIENT_SECRET = 'fake id'

    ADMINS = [
        'the-developer@example.com', # put your email here to get emails for some server errors.
    ]

    LOAD_DB_PARALLEL_PROCESSES = 8

class Config(BaseConfig):
    BROWSER_NAME = 'Bravo'
    DATASET_NAME = 'TOPMed'
    release = 'freeze2'
    NUM_SAMPLES = 6015

    GOOGLE_ANALYTICS_TRACKING_ID = 'UA-01234567-89'

    SHOW_POWERED_BY = True # whether to show the line "powered by <dataset_name>" on the homepage.

    # you should be able to run `mongo <host>:<port>/<name>` to get to your database.
    MONGO = {
        'host': 'localhost',
        'port': 27017,
        'name': 'topmed_freeze2',
    }

    BASE_COVERAGE = []
    for chrom in range(1,1+22):
        BASE_COVERAGE.append({
            'chrom': str(chrom),
            'min-length-bp': 0,
            'max-length-bp': 300,
            'path': '/var/browser_coverage/topmed_freeze2_random1000/full/{chrom}.topmed_freeze2.coverage.full.json.gz'.format(chrom=chrom),
        })
        BASE_COVERAGE.append({
            'chrom': str(chrom),
            'min-length-bp': 300,
            'max-length-bp': 1000,
            'path': '/var/browser_coverage/topmed_freeze2_random1000/bin_25e-2/{chrom}.topmed_freeze2.coverage.bin_25e-2.json.gz'.format(chrom=chrom),
        })
        BASE_COVERAGE.append({
            'chrom': str(chrom),
            'min-length-bp': 1000,
            'max-length-bp': sys.maxint,
            'path': '/var/browser_coverage/topmed_freeze2_random1000/bin_50e-2/{chrom}.topmed_freeze2.coverage.bin_50e-2.json.gz'.format(chrom=chrom),
        })
    BASE_COVERAGE.append({
        'chrom': 'X',
        'min-length-bp': 0,
        'max-length-bp': 300,
        'path': '/var/browser_coverage/topmed_freeze3a_public_X/X.topmed_freeze2.coverage.full2.json.gz' # original only went to 200k, not sure why.
    })
    BASE_COVERAGE.append({
        'chrom': 'X',
        'min-length-bp': 300,
        'max-length-bp': 1000,
        'path': '/var/browser_coverage/topmed_freeze3a_public_X/X.topmed_freeze2.coverage.bin_25e-2.json.gz'
    })
    BASE_COVERAGE.append({
        'chrom': 'X',
        'min-length-bp': 1000,
        'max-length-bp': 10000,
        'path': '/var/browser_coverage/topmed_freeze3a_public_X/X.topmed_freeze2.coverage.bin_50e-2.json.gz'
    })
    BASE_COVERAGE.append({
        'chrom': 'X',
        'min-length-bp': 10000,
        'max-length-bp': 100000,
        'path': '/var/browser_coverage/topmed_freeze3a_public_X/X.topmed_freeze2.coverage.bin_75e-2.json.gz'
    })
    BASE_COVERAGE.append({
        'chrom': 'X',
        'min-length-bp': 100000,
        'max-length-bp': sys.maxint,
        'path': '/var/browser_coverage/topmed_freeze3a_public_X/X.topmed_freeze2.coverage.bin_1e-0.json.gz'
    })

    _FILES_DIRECTORY = '/var/imported/topmed_freeze2'
    SITES_VCFS = glob.glob(os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'ALL.vcf.gz'))
    GENCODE_GTF = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'gencode.gtf.gz')
    CANONICAL_TRANSCRIPT_FILE = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'canonical_transcripts.txt.gz')
    OMIM_FILE = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'omim_info.txt.gz')
    DBNSFP_FILE = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'dbNSFP2.6_gene.gz')
    DBSNP_FILE=os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'dbsnp149.txt.bgz')

    EMAIL_WHITELIST = whitelist_topmed.whitelist # this is just a list of lowercase email addresses
