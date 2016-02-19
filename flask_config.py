# Note: Flask will only copy UPPERCASE variable names into `app.config`.

import sys
import os.path
import glob

class BaseConfig(object):
    DEBUG = False
    TESTING = False

    SECRET_KEY = 'development key'

    # Gotten from <https://console.developers.google.com/apis/credentials?project=genome-variant-server>
    # see the nice documentation at <https://support.google.com/cloud/answer/6158849?hl=en&ref_topic=6262490>
    GOOGLE_LOGIN_CLIENT_ID = 'fake key'
    GOOGLE_LOGIN_CLIENT_SECRET = 'fake id'

    ADMINS = [
        'pjvh@umich.edu',
    ]

    LOAD_DB_PARALLEL_PROCESSES = 8

class BravoConfig(BaseConfig):
    BROWSER_NAME = 'Bravo'
    DATASET_NAME = 'TOPMed'
    release = 'freeze2'
    NUM_SAMPLES = 6015

    GOOGLE_ANALYTICS_TRACKING_ID = 'UA-73910830-2'

    SHOW_POWERED_BY = True

    MONGO = {
        'host': 'localhost',
        'port': 27017,
        'name': 'topmed_freeze2',
    }

    BASE_COVERAGE = [
        {
            'min-length-bp': 0,
            'max-length-bp': 5000,
            'path': {str(chrom): '/var/browser_coverage/topmed_freeze2_random1000/full/{chrom}.topmed_freeze2.coverage.full.json.gz'.format(chrom=chrom) for chrom in range(1,1+22)},
        },
        {
            'min-length-bp': 5000,
            'max-length-bp': sys.maxint,
            'path': {str(chrom): '/var/browser_coverage/topmed_freeze2_random1000/bin_25e-2/{chrom}.topmed_freeze2.coverage.bin_25e-2.json.gz'.format(chrom=chrom) for chrom in range(1,1+22)},
        },
    ]

    _FILES_DIRECTORY = '/var/imported/topmed_freeze2'
    SITES_VCFS = glob.glob(os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'ALL.polymorphic.topmed_freeze2.vcf.gz')),
    GENCODE_GTF = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'gencode.gtf.gz'),
    CANONICAL_TRANSCRIPT_FILE = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'canonical_transcripts.txt.gz'),
    OMIM_FILE = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'omim_info.txt.gz'),
    BASE_COVERAGE_FILES = glob.glob(os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'coverage', 'Panel.*.coverage.txt.gz')),
    # How to get a snp141.txt.bgz file:
    #   wget http://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/snp141.txt.gz
    #   zcat snp141.txt.gz | cut -f 1-5 | bgzip -c > snp141.txt.bgz
    #   tabix -0 -s 2 -b 3 -e 4 snp141.txt.bgz

    #   wget ftp://ftp.ncbi.nlm.nih.gov/snp/organisms/human_9606_b142_GRCh37p13/database/organism_data/b142_SNPChrPosOnRef_105.bcp.gz
    #   zcat b142_SNPChrPosOnRef_105.bcp.gz | awk '$3 != ""' | perl -pi -e 's/ +/\t/g' | sort -k2,2 -k3,3n | bgzip -c > dbsnp142.txt.bgz
    #   tabix -s 2 -b 3 -e 3 dbsnp142.txt.bgz
    DBSNP_FILE=os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'dbsnp144.txt.bgz')

    EMAIL_WHITELIST = [
        # Developers
        "pjvh@umich.edu",
    ]
    EMAIL_WHITELIST = [email.lower() for email in EMAIL_WHITELIST]

class BravoTestConfig(BravoConfig):
    GOOGLE_ANALYTICS_TRACKING_ID = 'UA-73910830-1'

class InpsyghtConfig(BaseConfig):
    BROWSER_NAME = 'InPSYght Variant Browser'
    DATASET_NAME = 'InPSYght'
    NUM_SAMPLES = 735

    GOOGLE_ANALYTICS_TRACKING_ID = 'UA-73910830-3'

    SHOW_POWERED_BY = False

    MONGO = {
        'host': 'localhost',
        'port': 27017,
        'name': 'inpsyght',
    }

    BASE_COVERAGE = [
        {
            'min-length-bp': 0,
            'max-length-bp': 5000,
            'path': {str(chrom): '/var/browser_coverage/inpsyght_v1/full/{chrom}.inpsyght.coverage.full.json.gz'.format(chrom=chrom) for chrom in range(1,1+22)},
        },
        {
            'min-length-bp': 5000,
            'max-length-bp': 10000,
            'path': {str(chrom): '/var/browser_coverage/inpsyght_v1/bin_25e-2/{chrom}.inpsyght.coverage.bin_25e-2.json.gz'.format(chrom=chrom) for chrom in range(1,1+22)},
        },
        {
            'min-length-bp': 10000,
            'max-length-bp': sys.maxint,
            'path': {str(chrom): '/var/browser_coverage/inpsyght_v1/bin_50e-2/{chrom}.inpsyght.coverage.bin_50e-2.json.gz'.format(chrom=chrom) for chrom in range(1,1+22)},
        },
    ]

    _FILES_DIRECTORY = '/var/imported/inpsyght'
    SITES_VCFS = glob.glob(os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'ALL.polymorphic.topmed_freeze2.vcf.gz')),
    GENCODE_GTF = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'gencode.gtf.gz'),
    CANONICAL_TRANSCRIPT_FILE = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'canonical_transcripts.txt.gz'),
    OMIM_FILE = os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'omim_info.txt.gz'),
    BASE_COVERAGE_FILES = glob.glob(os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'coverage', 'Panel.*.coverage.txt.gz')),
    # How to get a snp141.txt.bgz file:
    #   wget http://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/snp141.txt.gz
    #   zcat snp141.txt.gz | cut -f 1-5 | bgzip -c > snp141.txt.bgz
    #   tabix -0 -s 2 -b 3 -e 4 snp141.txt.bgz

    #   wget ftp://ftp.ncbi.nlm.nih.gov/snp/organisms/human_9606_b142_GRCh37p13/database/organism_data/b142_SNPChrPosOnRef_105.bcp.gz
    #   zcat b142_SNPChrPosOnRef_105.bcp.gz | awk '$3 != ""' | perl -pi -e 's/ +/\t/g' | sort -k2,2 -k3,3n | bgzip -c > dbsnp142.txt.bgz
    #   tabix -s 2 -b 3 -e 3 dbsnp142.txt.bgz
    DBSNP_FILE=os.path.join(os.path.dirname(__file__), _FILES_DIRECTORY, 'dbsnp144.txt.bgz')

    EMAIL_WHITELIST = [
        # Developers
        "pjvh@umich.edu",
    ]
    EMAIL_WHITELIST = [email.lower() for email in EMAIL_WHITELIST]

class InpsyghtTestConfig(InpsyghtConfig):
    GOOGLE_ANALYTICS_TRACKING_ID = 'UA-73910830-1'
