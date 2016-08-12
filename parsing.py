"""
Utils for reading flat files that are loaded into database
"""
import re
import traceback
from utils import *

POPS = {
    'AFR': 'African',
    'AMR': 'Latino',
    'EAS': 'East Asian',
    'FIN': 'European (Finnish)',
    'NFE': 'European (Non-Finnish)',
    'SAS': 'South Asian',
    'OTH': 'Other'
}


def get_base_coverage_from_file(base_coverage_file):
    """
    Read a base coverage file and return iter of dicts that look like:
    {
        'xpos': 1e9+1,
        'mean': 0.0,
        'median': 0.0,
        '1': 0.0,
        '5': 0.0,
        '10': 0.0,
        '15': 0.0,
        '20': 0.0,
        '25': 0.0,
        '30': 0.0,
        '50': 0.0,
        '100': 0.0,
    }
    """

    float_header_fields = ['mean', 'median', '1', '5', '10', '15', '20', '25', '30', '50', '100']
    for line in base_coverage_file:
        if line.startswith('#'):
            continue
        fields = line.strip('\n').split('\t')
        d = {
            'xpos': get_xpos(fields[0], int(fields[1])),
            'pos': int(fields[1]),
        }
        for i, k in enumerate(float_header_fields):
            d[k] = float(fields[i+2])
        yield d


def get_variants_from_sites_vcf(sites_vcf):
    """
    Parse exac sites VCF file and return iter of variant dicts
    sites_vcf is a file (gzipped), not file path
    """

    # DT: dirty temporary fill-in:
    #dp_mids = map(float, '2.5|7.5|12.5|17.5|22.5|27.5|32.5|37.5|42.5|47.5|52.5|57.5|62.5|67.5|72.5|77.5|82.5|87.5|92.5|97.5'.split('|'))
    #gq_mids = map(float, '2.5|7.5|12.5|17.5|22.5|27.5|32.5|37.5|42.5|47.5|52.5|57.5|62.5|67.5|72.5|77.5|82.5|87.5|92.5|97.5'.split('|'))
    #hists_all = ['0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0', '0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0']

    vep_field_names = None
    for line in sites_vcf:
        try:
            line = line.strip('\n')
            if line.startswith('##INFO=<ID=CSQ'):
                vep_field_names = line.split('Format: ')[-1].strip('">').split('|')
            if line.startswith('##INFO=<ID=DP_HIST'):
                dp_mids = map(float, line.split('Mids: ')[-1].strip('">').split('|'))
            if line.startswith('##INFO=<ID=GQ_HIST'):
                gq_mids = map(float, line.split('Mids: ')[-1].strip('">').split('|'))
            if line.startswith('#'):
                continue

            # If we get here, it's a variant line
            if vep_field_names is None:
                raise Exception("VEP_field_names is None. Make sure VCF header is present.")
            # This elegant parsing code below is copied from https://github.com/konradjk/loftee
            fields = line.split('\t')
            info_field = dict([(x.split('=', 1)) if '=' in x else (x, x) for x in re.split(';(?=\w)', fields[7])])
            consequence_array = info_field['CSQ'].split(',') if 'CSQ' in info_field else []
            annotations = [dict(zip(vep_field_names, x.split('|'))) for x in consequence_array if len(vep_field_names) == len(x.split('|'))]
            #DT: we will store anotations for all variants (not only for exonic)
            #coding_annotations = [ann for ann in annotations if ann['Feature'].startswith('ENST')]

            alt_alleles = fields[4].split(',')

            # different variant for each alt allele
            for i, alt_allele in enumerate(alt_alleles):

                #DT: we will store anotations for all variants (not only for exonic)
                #vep_annotations = [ann for ann in coding_annotations if int(ann['ALLELE_NUM']) == i + 1]
                vep_annotations = [ann for ann in annotations if int(ann['ALLELE_NUM']) == i + 1]

                # Variant is just a dict
                # Make a copy of the info_field dict - so all the original data remains
                # Add some new keys that are allele-specific
                pos, ref, alt = get_minimal_representation(fields[1], fields[3], alt_allele)

                variant = {}
                variant['chrom'] = fields[0]
                variant['pos'] = pos

                #DT: We will take rsIds and CADD from the VEP annotation
                #variant['rsid'] = fields[2]

                variant['cadd_raw'] = None if not 'CADD_RAW' in info_field else float(info_field['CADD_RAW'].split(',')[i])
                variant['cadd_phred'] = None if not 'CADD_PHRED' in info_field else float(info_field['CADD_PHRED'].split(',')[i])

                if vep_annotations:
                   variant['rsids'] = list(rsid for rsid in vep_annotations[0]['Existing_variation'].split('&') if rsid.startswith("rs"))
                   #variant['cadd_raw'] = None if not vep_annotations[0]['CADD_RAW'] else float(vep_annotations[0]['CADD_RAW']) 
                   #variant['cadd_phred'] = None if not vep_annotations[0]['CADD_PHRED'] else float(vep_annotations[0]['CADD_PHRED'])
                else:
                   variant['rsids'] = []
                   #variant['cadd_raw'] = None
                   #variant['cadd_phred'] = None
                   
                variant['xpos'] = get_xpos(variant['chrom'], variant['pos'])
                variant['ref'] = ref
                variant['alt'] = alt
                variant['xstart'] = variant['xpos']
                variant['xstop'] = variant['xpos'] + len(variant['alt']) - len(variant['ref'])
                variant['variant_id'] = '{}-{}-{}-{}'.format(variant['chrom'], variant['pos'], variant['ref'], variant['alt'])
                variant['orig_alt_alleles'] = [
                    '{}-{}-{}-{}'.format(variant['chrom'], *get_minimal_representation(fields[1], fields[3], x))
                    for x in alt_alleles
                ]
                variant['site_quality'] = float(fields[5])
                variant['filter'] = fields[6]
                variant['vep_annotations'] = vep_annotations

                # DT: variant['allele_count'] = int(info_field['AC_Adj'].split(',')[i])
                variant['allele_count'] = int(info_field['AC'].split(',')[i])
                # DT: if not variant['allele_count'] and variant['filter'] == 'PASS': variant['filter'] = 'AC_Adj0' # Temporary filter
                # DT: variant['allele_num'] = int(info_field['AN_Adj'])
                variant['allele_num'] = int(info_field['AN'])
                # DT: if variant['allele_num'] > 0:
                # DT:    variant['allele_freq'] = variant['allele_count']/float(info_field['AN_Adj'])
                # DT: else:
                variant['allele_freq'] = float(info_field['AF'].split(',')[i])

                # DT: variant['pop_acs'] = dict([(POPS[x], int(info_field['AC_%s' % x].split(',')[i])) for x in POPS])
                variant['pop_acs'] = dict([(POPS[x], 0) for x in POPS])
                # DT: variant['pop_ans'] = dict([(POPS[x], int(info_field['AN_%s' % x])) for x in POPS])
                variant['pop_ans'] = dict([(POPS[x], 0) for x in POPS])
                # DT: variant['pop_homs'] = dict([(POPS[x], int(info_field['Hom_%s' % x].split(',')[i])) for x in POPS])
                variant['pop_homs'] = dict([(POPS[x], 0) for x in POPS])
                # DT: variant['hom_count'] = sum(variant['pop_homs'].values())
                variant['hom_count'] = int(info_field['Hom'].split(',')[i])
                if variant['chrom'] in ('X', 'Y'):
                # DT: variant['pop_hemis'] = dict([(POPS[x], int(info_field['Hemi_%s' % x].split(',')[i])) for x in POPS])
                    variant['pop_hemis'] = dict([(POPS[x], 0) for x in POPS])
                    variant['hemi_count'] = sum(variant['pop_hemis'].values())
                variant['quality_metrics'] = dict([(x, info_field[x]) for x in METRICS if x in info_field])

                variant['genes'] = list({annotation['Gene'] for annotation in vep_annotations})
                variant['transcripts'] = list({annotation['Feature'] for annotation in vep_annotations})

                if 'DP_HIST' in info_field:
                   hists_all = [info_field['DP_HIST'].split(',')[0], info_field['DP_HIST'].split(',')[i+1]]
                   variant['genotype_depths'] = [zip(dp_mids, map(int, x.split('|'))) for x in hists_all]
                if 'GQ_HIST' in info_field:
                   hists_all = [info_field['GQ_HIST'].split(',')[0], info_field['GQ_HIST'].split(',')[i+1]]
                   variant['genotype_qualities'] = [zip(gq_mids, map(int, x.split('|'))) for x in hists_all]
                
                # DT: dirty temporary fill-in:
                # DT: variant['genotype_depths'] = [zip(dp_mids, map(int, x.split('|'))) for x in hists_all]
                # DT: variant['genotype_qualities'] = [zip(gq_mids, map(int, x.split('|'))) for x in hists_all] 

                yield variant
        except Exception:
            print("Error parsing vcf line: " + line)
            traceback.print_exc()
            break


def get_canonical_transcripts(canonical_transcript_file):
    for line in canonical_transcript_file:
        gene, transcript = line.strip().split()
        yield gene, transcript


def get_omim_associations(omim_file):
    for line in omim_file:
        fields = line.strip().split('\t')
        if len(fields) == 4:
            yield fields
        else:
            yield None


def get_genes_from_gencode_gtf(gtf_file):
    """
    Parse gencode GTF file;
    Returns iter of gene dicts
    """
    for line in gtf_file:
        if line.startswith('#'):
            continue
        fields = line.strip('\n').split('\t')

        if fields[2] != 'gene':
            continue

        chrom = fields[0][3:]
        start = int(fields[3]) + 1  # bed files are 0-indexed
        stop = int(fields[4]) + 1
        info = dict(x.strip().split() for x in fields[8].split(';') if x != '')
        info = {k: v.strip('"') for k, v in info.items()}
        gene_id = info['gene_id'].split('.')[0]

        gene = {
            'gene_id': gene_id,
            'gene_name': info['gene_name'],
            'gene_name_upper': info['gene_name'].upper(),
            'chrom': chrom,
            'start': start,
            'stop': stop,
            'strand': fields[6],
            'xstart': get_xpos(chrom, start),
            'xstop': get_xpos(chrom, stop),
        }
        yield gene


def get_transcripts_from_gencode_gtf(gtf_file):
    """
    Parse gencode GTF file;
    Returns iter of transcript dicts
    """
    for line in gtf_file:
        if line.startswith('#'):
            continue
        fields = line.strip('\n').split('\t')

        if fields[2] != 'transcript':
            continue

        chrom = fields[0][3:]
        start = int(fields[3]) + 1  # bed files are 0-indexed
        stop = int(fields[4]) + 1
        info = dict(x.strip().split() for x in fields[8].split(';') if x != '')
        info = {k: v.strip('"') for k, v in info.items()}
        transcript_id = info['transcript_id'].split('.')[0]
        gene_id = info['gene_id'].split('.')[0]

        gene = {
            'transcript_id': transcript_id,
            'gene_id': gene_id,
            'chrom': chrom,
            'start': start,
            'stop': stop,
            'strand': fields[6],
            'xstart': get_xpos(chrom, start),
            'xstop': get_xpos(chrom, stop),
        }
        yield gene


def get_exons_from_gencode_gtf(gtf_file):
    """
    Parse gencode GTF file;
    Returns iter of transcript dicts
    """
    for line in gtf_file:
        if line.startswith('#'):
            continue
        fields = line.strip('\n').split('\t')

        if fields[2] not in ['exon', 'CDS', 'UTR']:
            continue

        chrom = fields[0][3:]
        feature_type = fields[2]
        start = int(fields[3]) + 1  # bed files are 0-indexed
        stop = int(fields[4]) + 1
        info = dict(x.strip().split() for x in fields[8].split(';') if x != '')
        info = {k: v.strip('"') for k, v in info.items()}
        transcript_id = info['transcript_id'].split('.')[0]
        gene_id = info['gene_id'].split('.')[0]

        exon = {
            'feature_type': feature_type,
            'transcript_id': transcript_id,
            'gene_id': gene_id,
            'chrom': chrom,
            'start': start,
            'stop': stop,
            'strand': fields[6],
            'xstart': get_xpos(chrom, start),
            'xstop': get_xpos(chrom, stop),
        }
        yield exon


def get_dbnsfp_info(dbnsfp_file):
    """
    Parse dbNSFP_gene file;
    Returns iter of transcript dicts
    """
    header = dbnsfp_file.next().split('\t')
    fields = dict(zip(header, range(len(header))))
    for line in dbnsfp_file:
        line = line.split('\t')
        other_names = line[fields["Gene_old_names"]].split(';') if line[fields["Gene_old_names"]] != '.' else []
        if line[fields["Gene_other_names"]] != '.':
            other_names.extend(line[fields["Gene_other_names"]].split(';'))
        gene_info = {
            'gene_name': line[fields["Gene_name"]],
            'ensembl_gene': line[fields["Ensembl_gene"]],
            'gene_full_name': line[fields["Gene_full_name"]],
            'gene_other_names': other_names
        } 
        yield gene_info


def get_snp_from_dbsnp_file(dbsnp_file):
    for line in dbsnp_file:
        fields = line.split('\t')
        if len(fields) < 3: continue
        rsid = int(fields[0])
        chrom = fields[1].rstrip('T')
        if chrom == 'PAR': continue
        start = int(fields[2]) + 1
        snp = {
            'xpos': get_xpos(chrom, start),
            'rsid': rsid
        }
        yield snp
