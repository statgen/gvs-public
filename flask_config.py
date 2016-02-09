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

    administrators = [
        'pjvh@umich.edu',
        'dtaliun@umich.edu',
    ]

    examples = {
        'gene': 'APOL1',
        'transcript': 'ENST00000407236',
        'variant': '22-46615880-T-C',
        'multi-allelic-variant': 'rs1800234',
        'region': '22:46615715-46615880',
    }

    pass_only_variants = False

    LOAD_DB_PARALLEL_PROCESSES = 8

class BravoConfig(BaseConfig):
    name = 'Bravo'
    dataset_name = 'TOPMED'
    _release = 'freeze2'
    num_samples = 6015

    mongo = {
        'host': 'localhost',
        'port': '27017',
        'name': 'topmed_freeze2',
    }

    base_coverage = [
        {
            'min-length-bp': 0,
            'max-length-bp': 5000,
            'path': {str(i): '/var/browser_coverage/topmed_freeze2_random1000/full/{}.topmed_freeze2.coverage.full.json.gz'.format(i) for i in range(1,1+22)},
        },
        {
            'min-length-bp': 5000,
            'max-length-bp': sys.maxint,
            'path': {str(i): '/var/browser_coverage/topmed_freeze2_random1000/bin_25e-2/{}.topmed_freeze2.coverage.bin_25e-2.json.gz'.format(i) for i in range(1,1+22)},
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
