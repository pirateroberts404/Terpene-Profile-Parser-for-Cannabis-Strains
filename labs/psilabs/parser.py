#!/usr/bin/env python3
# coding: utf-8
#
'''
TODO:
test metadata
Normalization:
	cannabinoids total
	sample type
	test metadata

use skip_this_file more
'''
DATA_ROW_FIELDS = [
	'Test Result UID',
	'Sample Name',
	'Sample Type',
	'Receipt Time',
	'Test Time',
	'Provider',
	'cis-Nerolidol',
	'trans-Nerolidol',
	'trans-Nerolidol 1',
	'trans-Nerolidol 2',
	'trans-Ocimene',
	'delta-3-Carene',
	'Camphene',
	'Caryophyllene Oxide',
	'Eucalyptol',
	'Geraniol',
	'Guaiol',
	'Isopulegol',
	'Linalool',
	'Ocimene',
	'Terpinolene',
	'alpha-Bisabolol',
	'alpha-Humulene',
	'alpha-Pinene',
	'alpha-Terpinene',
	'beta-Caryophyllene',
	'beta-Myrcene',
	'beta-Ocimene',
	'beta-Pinene',
	'delta-Limonene',
	'gamma-Terpinene',
	'p-Cymene',
	'delta-9 THC-A',
	'delta-9 THC',
	'delta-8 THC',
	'THC-A',
	'THCV',
	'CBN',
	'CBD-A',
	'CBD',
	'delta-9 CBG-A',
	'delta-9 CBG',
	'CBG-A',
	'CBG',
	'CBC',
	'Moisture Content',
]
import re, os, csv, argparse, json, urllib, datetime, logging
from lxml import html
from lxml import etree
import dateparser.search as dateparser_search

parser = argparse.ArgumentParser(argument_default=False, description='Clean raw lab data.')
parser.add_argument('database', nargs='?', default='downloader/database_dump/', help='The location of the database dump.')
parser.add_argument('--verbose', '-v', action='count', default=0, help='Turn on verbose mode.')
parser.add_argument('--json', action='store_true', help='Export as JSON.')
parser.add_argument('--csv', action='store_true', help='Export as CSV.')
parser.add_argument('--log', help='Logfile path. If omitted, stdout is used.')
parser.add_argument('--debug', '-d', action='store_true', help='Log all messages including debug.')
parser.add_argument('--force-terpenes', action='store_true', help='Skip all samples without a terpene profile.')
parser.add_argument('--force-cannabinoids', action='store_true', help='Skip all samples without a cannabinoid profile.')
parser.add_argument('--placeholder-csv', default='', help='CSV only: The placeholder to use when no value is present.')
args = parser.parse_args()

if args.debug:
	loglevel = logging.DEBUG
elif args.verbose:
	loglevel = logging.INFO
else:
	loglevel = logging.WARNING

if args.log:
	logging.basicConfig(filename=args.log, filemode='a', level=loglevel)
else:
	logging.basicConfig(level=loglevel)

def get_single_value(tree, xpath, fallback=None, errlevel=logging.CRITICAL, errmsg=None, errparams=[], join_multi=False):
	raw_value = tree.xpath(xpath)
	if len(raw_value) == 1:
		if type(raw_value[0]) == str or type(raw_value[0]) == etree._ElementUnicodeResult:
			return raw_value[0].strip()
		else:
			return raw_value[0]
	else:
		if join_multi == False:
			if errmsg:
				logging.log(errlevel, errmsg, *errparams)
			return fallback
		else:
			if type(join_multi) == str:
				return join_multi.join(raw_value).strip()
			else:
				return ''.join(raw_value).strip()

def normalize_number(numberstring, base=10, comma=False, separator=False, compress=False):
	dots = numberstring.count('.')
	commas = numberstring.count(',')
	# multiple = more than 1
	# single = 1
	# zero = 0
	## multiple commas, multiple dots:		ERROR
	if commas > 1 and dots > 1:
		raise ValueError("could not convert string to float: '{}'".format(numberstring))
	# AMERICAN
	## multiple commas, single dot:			remove commas, float
	## multiple commas, zero dots:			remove commas, float (int)
	## no commas, single dot:				float
	if (commas > 1 and dots <= 1) or (commas == 0 and dots == 1):
		decimal = '.'
	# EUROPEAN
	## single comma, multiple dots:			remove dots, float
	## zero commas, multiple dots:			remove dots, float (int)
	## single comma, no dots:				float
	if (dots > 1 and commas <= 1) or (dots == 0 and commas == 1):
		decimal = ','
	numberstring = re.sub(r'[^0-9{}]'.format(decimal), '', numberstring)
	numberstring = numberstring.replace(decimal, '.')
	result = float(numberstring)
	if compress:
		if result == '0.0':
			return '0'
		elif result.startswith('0.'):
			return result[1:]
	return result

def csv_escape(data):
	return '"{}"'.format(data)

def write_to_csv(filepath, fieldnames, data):
	if os.path.exists(filepath):
		writeheader = False
	else:
		writeheader = True
	with open(filepath, 'a', encoding='utf-8') as writefile:
		writefile_writer = csv.DictWriter(writefile, fieldnames=fieldnames, restval=args.placeholder_csv, lineterminator='\n')
		if writeheader:
			writefile_writer.writeheader()
		if type(data) != list:
			data = [data]
		for data_row in data:
			writefile_writer.writerow(data_row)

def test_match(xpath_here):
	matches = tree.xpath(xpath_here)
	if len(matches) > 0:
		logging.debug('Match!')
	for i in matches:
		logging.debug('Tag: %s', i.tag)
		logging.debug('Attribs: %s', i.attrib)

logging.debug('Loading configurations . . .')

xpath_provider_page = """"""

xpath_festival_page = """"""

# Finds the list items of the terpene test
xpath_terpenes_1 =				'/html/body/ui-view/div/md-content/ui-view/div/md-content/div/md-card[@ng-if="Sample.details.terpeneTestComplete"]/div/div/md-table-container/table[thead/tr[th[1][text()="Terpene"]][th[2][text()="Amount"]]]/tbody/tr'

# Finds the amount of total terpenes present in the sample
xpath_terpenes_total =			'/html/body/ui-view/div/md-content/ui-view/div/md-content/div/md-card[@ng-if="Sample.details.terpeneTestComplete"]/md-card-header/md-card-header-text/span[text()=" Total Terpenes "]/preceding-sibling::span[@class="md-title"]/text()'

# Finds the list items of the cannabinoid test
xpath_cannabinoids_1 =			'/html/body/ui-view/div/md-content/ui-view/div/md-content/div/md-card[@ng-if="Sample.details.potencyTestComplete"]/div/div/md-table-container/table[thead/tr[th[1][text()="Cannabinoid"]][th[2][text()="Amount"]][th[3][text()="Uncertainty"]]]/tbody/tr'

# Finds the amount of total THC present in the sample
xpath_thc_total =				'/html/body/ui-view/div/md-content/ui-view/div/md-content/div/md-card[@ng-if="Sample.details.potencyTestComplete"]/md-card-header/md-card-header-text/span[text()="Total THC"][@ng-show="Sample.details.totalTHC"]/preceding-sibling::span[1][@ng-show="Sample.details.totalTHC"]/text()'

# Finds the amount of total CBD present in the sample
xpath_cbd_total =				'/html/body/ui-view/div/md-content/ui-view/div/md-content/div/md-card[@ng-if="Sample.details.potencyTestComplete"]/md-card-header/md-card-header-text/span[text()="Total CBD"][@ng-show="Sample.details.totalCBD"]/preceding-sibling::span[1][@ng-show="Sample.details.totalCBD"]/text()'

# Finds the type of the sample
xpath_sample_type =				'/html/body/ui-view/div/md-content/ui-view/div/md-content/div[1]/md-card[1]/md-card-header/md-card-header-text/span[1][following-sibling::span[1][@class="md-title"]]/text()'

# Finds the name of the sample
xpath_sample_name =				'/html/body/ui-view/div/md-content/ui-view/div/md-content/div[1]/md-card[1]/md-card-header/md-card-header-text/span[@class="md-title"]/text()'

# Finds the provider of the sample
xpath_sample_provider =			'/html/body/ui-view/div/md-content/ui-view/div/md-content/div[1]/md-card[1]/md-card-header/md-card-header-text/span[@class="md-subhead"][@ng-if="Sample.details.clientInformation.clientId"]/a/text()'
xpath_sample_provider_anon =	'/html/body/ui-view/div/md-content/ui-view/div/md-content/div[1]/md-card[1]/md-card-header/md-card-header-text/span[@class="md-subhead"][@ng-if="!Sample.details.clientInformation.clientId"]/text()'

xpath_test_uid = """/html/body/ui-view/div/md-content/ui-view/div/md-content/div/md-card/md-card-content/a[
						starts-with(
							translate(
								normalize-space(@href),
								'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
								'abcdefghijklmnopqrstuvwxyz'
							),
							'/results/samples/edit/'
						)
					]/@href"""

# Finds the timestamp of the test of the sample
xpath_time_tested =				'/html/body/ui-view/div/md-content/ui-view/div/md-content/div[2]/md-card[1]/md-card-content/md-list/md-list-item/span/h3[following-sibling::p[text()="Date Tested"]]/text()'
# Finds the timestamp of receipt of the sample
xpath_time_received =			'/html/body/ui-view/div/md-content/ui-view/div/md-content/div[2]/md-card[1]/md-card-content/md-list/md-list-item/span/h3[following-sibling::p[text()="Date Received"]]/text()'

terpenes = {
	'delta-3-Carene':		re.compile(r'^(delta)?[-_/\s.]*(3|Three|Tri)[-_/\s.]*Carene$',	re.IGNORECASE),
	'Camphene':				re.compile(r'^Camphene$',										re.IGNORECASE),
	'Caryophyllene Oxide':	re.compile(r'^Caryophyllene[-_/\s.]*Oxide$',					re.IGNORECASE),
	'Eucalyptol':			re.compile(r'^Eucalyptol$',										re.IGNORECASE),
	'Farnesene': 			re.compile(r'^Farnesene$',										re.IGNORECASE),
	'Geraniol':				re.compile(r'^Geraniol$',										re.IGNORECASE),
	'Guaiol':				re.compile(r'^Guaiol$',											re.IGNORECASE),
	'Isopulegol':			re.compile(r'^(\(-\)[-_/\s.]+)?Isopulegol$',					re.IGNORECASE),
	'Linalool':				re.compile(r'^Linalool$',										re.IGNORECASE),
	'Ocimene':				re.compile(r'^Ocimene$',										re.IGNORECASE),
	'Terpinolene':			re.compile(r'^Terpinolene$',									re.IGNORECASE),
	'alpha-Bisabolol':		re.compile(r'^(alpha|A|α)[-_/\s.]*Bisabolol$',					re.IGNORECASE),
	'alpha-Humulene':		re.compile(r'^(alpha|A|α)?[-_/\s.]*Humulene$',					re.IGNORECASE),
	'alpha-Pinene':			re.compile(r'^(alpha|A|α)[-_/\s.]*Pinene$',						re.IGNORECASE),
	'beta-Pinene':			re.compile(r'^(beta|B|β)[-_/\s.]*Pinene$',						re.IGNORECASE),
	'alpha-Terpinene':		re.compile(r'^(alpha|A|α)[-_/\s.]*Terpinene$',					re.IGNORECASE),
	'beta-Caryophyllene':	re.compile(r'^(beta|B|β)?[-_/\s.]*Caryophyllene$',				re.IGNORECASE),
	'beta-Myrcene':			re.compile(r'^(beta|B|β)?[-_/\s.]*Myrcene$',					re.IGNORECASE),
	'beta-Ocimene':			re.compile(r'^(beta|B|β)[-_/\s.]*Ocimene$',						re.IGNORECASE),
	'cis-Nerolidol':		re.compile(r'^(cis)[-_/\s.]*Nerolidol$',						re.IGNORECASE),
	'delta-Limonene':		re.compile(r'^(delta|D|δ)?[-_/\s.]*Limonene$',					re.IGNORECASE),
	'gamma-Terpinene':		re.compile(r'^(gamma|G|Y|γ)[-_/\s.]*Terpinene$',				re.IGNORECASE),
	'p-Cymene':				re.compile(r'^(p)[-_/\s.]*Cymene$',								re.IGNORECASE),
	'trans-Nerolidol':		re.compile(r'^(trans)[-_/\s.]*Nerolidol$',						re.IGNORECASE),
	'trans-Nerolidol 1':	re.compile(r'^(trans)[-_/\s.]*Nerolidol[-_/\s.]*1$',			re.IGNORECASE),
	'trans-Nerolidol 2':	re.compile(r'^(trans)[-_/\s.]*Nerolidol[-_/\s.]*2$',			re.IGNORECASE),
	'trans-Ocimene':		re.compile(r'^(trans)[-_/\s.]*Ocimene$',						re.IGNORECASE),
}
terpenes['Terpene TOTAL'] = re.compile(r'^(Terpene[-_/\s.]*TOTAL|Total[-_/\s.]*[-_/\s.]*Terpenes)',re.IGNORECASE)

cannabinoids = {
	'delta-9 THC-A':		re.compile(r'^(delta|Δ|∆)[-_/\s.]*9[-_/\s.]*THC[-_/\s.]*A$',	re.IGNORECASE),
	'delta-9 THC':			re.compile(r'^(delta|Δ|∆)[-_/\s.]*9[-_/\s.]*THC$',				re.IGNORECASE),
	'CBN':					re.compile(r'^CBN$',											re.IGNORECASE),
	'CBD-A':				re.compile(r'^CBD[-_/\s.]*A$',									re.IGNORECASE),
	'CBD':					re.compile(r'^CBD$',											re.IGNORECASE),
	'CBG-A':				re.compile(r'^CBG[-_/\s.]*A$',									re.IGNORECASE),
	'CBG':					re.compile(r'^CBG$',											re.IGNORECASE),
	'delta-9 CBG-A':		re.compile(r'^(delta|Δ|∆)[-_/\s.]*9[-_/\s.]*CBG[-_/\s.]*A$',	re.IGNORECASE),
	'delta-9 CBG':			re.compile(r'^(delta|Δ|∆)[-_/\s.]*9[-_/\s.]*CBG$',				re.IGNORECASE),
	'CBC':					re.compile(r'^CBC$',											re.IGNORECASE),
	'THCV':					re.compile(r'^THCV$',											re.IGNORECASE),
	'delta-8 THC':			re.compile(r'^(delta|Δ|∆)[-_/\s.]*8[-_/\s.]*THC$',				re.IGNORECASE),
	'Moisture Content':		re.compile(r'^Moisture[-_/\s.]*[-_/\s.]+Content$',				re.IGNORECASE),
	'THC-A':				re.compile(r'^THC[-_/\s.]*A$',									re.IGNORECASE),
}
cannabinoids['THC TOTAL'] = re.compile(r'^THC[-_/\s.]*TOTAL',								re.IGNORECASE)
cannabinoids['delta-9 THC TOTAL'] = re.compile(r'^(delta|Δ|∆)[-_/\s.]*9[-_/\s.]*THC[-_/\s.]*TOTAL$',re.IGNORECASE)
cannabinoids['CBD TOTAL'] = re.compile(r'^CBD[-_/\s.]*TOTAL',								re.IGNORECASE)
cannabinoids['CBG TOTAL'] = re.compile(r'^CBG[-_/\s.]*TOTAL',								re.IGNORECASE)
cannabinoids['Activated TOTAL'] = re.compile(r'^Activated[-_/\s.]*TOTAL',					re.IGNORECASE)
cannabinoids['Cannabinoids TOTAL'] = re.compile(r'^TOTAL[-_/\s.]*CANNABINOIDS',				re.IGNORECASE)

sample_types = {
	'Flower':				re.compile(r'^Flowers?$',										re.IGNORECASE),
	'Concentrate':			re.compile(r'^Concentrates?$',									re.IGNORECASE),
	'Edible':				re.compile(r'^Edibles?$',										re.IGNORECASE),
	'Liquid':				re.compile(r'^Liquids?$',										re.IGNORECASE),
	'Topical':				re.compile(r'^Topicals?$',										re.IGNORECASE),
}
sample_types['Edible Concentrate'] = re.compile(r'^Edible[-_/\s.]*Concentrate$',			re.IGNORECASE)
sample_types['Infusion'] =				re.compile(r'^Infusion$',							re.IGNORECASE)

re_test_uid = re.compile(r'^/results/samples/edit/(?P<uid>[_a-zA-Z0-9]+)$')

# Parses an american timestamp into its meaningful parts
re_date =			re.compile(r'^(?P<date>\s*(?P<month>(0?[0-9]|1[0-2]))\s*[-\./:]?\s*(?P<day>(0?[0-9]|1[0-9]|2[0-9]|3[0-1]))\s*[-\./:]?\s*(?P<year>(2\d{3}|[013-9][0-9])))$', re.IGNORECASE)

# Match a percentage value
re_percentageValue = re.compile(r'^[0-9.,]+\s*%$')
# Match a percentage value
re_zeroPercentageValue = re.compile(r'^<\s*[0-9.,]+\s*%$')
# Match a percentage value at the beginning of the string
re_percentageValueBeginning = re.compile(r'^[0-9.,]+\s*%')
# Match a (zero) percentage value at the beginning of the string
re_zeroPercentageValueBeginning = re.compile(r'^<\s*[0-9.,]+\s*%')

database = {
}

# database = {
# 	"name": "Psilabs",
# 	"samples": []
# }

providers = []
sample_types_all = []
empty_terpenes_counter = 0
empty_cannabinoid_counter = 0

sample_database_CSVfile = 'results.csv'
sample_database_JSONfile = 'results.json'

if input('\nDo you want to delete the old result and log files? (y/n) ').lower() == 'y':
	if os.path.exists(filename+'.csv'):
		os.remove(filename+'.csv')
	if os.path.exists(sample_database_CSVfile):
		os.remove(sample_database_CSVfile)
	if os.path.exists(sample_database_JSONfile):
		os.remove(sample_database_JSONfile)

print('Before we start, a heads up:',
		'I will try to extract any terpene and cannabinoid profiles present as exact as possible. Samples which have values in ppm or mg units are skipped.',
		'If a specific terpene is not present, I will ignore it for that page',
		sep='\n'
		)
if input('\nDo you want to start? (y/n) ').lower() != 'y':
	exit('Aborted.')

if args.json:
	with open(sample_database_JSONfile, "w", encoding="utf-8") as databases_file:
		databases_file.write('{"name":"Psilabs"')
		databases_file.write(',"samples":{')

logging.debug('Entering main loop . . .')

type_folders = sorted(os.listdir(os.path.expanduser(args.database)))
is_first_type = True
for type_index, type_folder in enumerate(type_folders):
	is_first_sample = True
	file_list = sorted(os.listdir(os.path.join(os.path.expanduser(args.database),type_folder)))
	if args.json:
		with open(sample_database_JSONfile, "a", encoding="utf-8") as databases_file:
			if not is_first_type:
				databases_file.write(',')
			databases_file.write('"{}":['.format(type_folder))
			is_first_type = False
	for file_index, file_name in enumerate(file_list):
		raw_sample_file_name = os.path.join(type_folder, file_name)
		logging.debug('#'*80)

		logging.info('%s: Started parsing.', raw_sample_file_name)
		with open(os.path.join(os.path.expanduser(args.database),raw_sample_file_name),encoding='utf-8') as raw_sample_file:
			tree = html.fromstring(raw_sample_file.read())

		skip_this_file = False


		# 0 Test Data terpenes
		raw_terpenes_1 = tree.xpath(xpath_terpenes_1)
		terpenes_data = {}
		non_percentage_numbers = False
		# if len(raw_terpenes_1) > 0:
		# 	logging.warning('%s: Both terpenes queries match!', raw_sample_file_name)
		if 0 == len(raw_terpenes_1):
			logging.warning('%s: No terpenes.', raw_sample_file_name)
		else:
			for i, raw_terpene in enumerate(raw_terpenes_1, 1):

				# AMOUNT
				raw_terpene_amount = get_single_value(
					tree=raw_terpene,
					xpath='td[2]/text()',
					fallback=''
				)
				terpene_amount_match = re_percentageValue.match(raw_terpene_amount)
				terpene_zeroamount_match = re_zeroPercentageValue.match(raw_terpene_amount)
				if terpene_amount_match:
					terpene_amount_match_object = terpene_amount_match
					try:
						terpene_amount = normalize_number(
							numberstring=raw_terpene_amount[terpene_amount_match.start():terpene_amount_match.end()]
						)
					except ValueError as e:
						logging.warning('%s: Terpenes number error: %s (at list index %d).', raw_sample_file_name, raw_terpene_amount, i)
						continue
				elif terpene_zeroamount_match:
					terpene_amount_match_object = terpene_zeroamount_match
					terpene_amount = 0.0
				else:
					non_percentage_numbers = True
					logging.info('%s: Non-percentage terpene (at list index %d).', raw_sample_file_name, i)
					continue

				# NAME
				## TODO: we could do levenshtein- and typewriterdistance (en-US) here
				original_terpene_name = get_single_value(
					tree=raw_terpene,
					xpath='td[1]/text()',
					fallback=''
				)
				regex_matched = False
				for terpene_name in terpenes.keys():
					terpene_regex = terpenes[terpene_name]
					logging.debug('%s: Trying Regex "%s".', raw_sample_file_name, terpene_regex.pattern)
					terpene_match = terpene_regex.match(original_terpene_name)
					if terpene_match:
						logging.debug('%s: Terpene matched Regex "%s".', original_terpene_name, terpene_regex)
						if regex_matched:
							# Match more than one regex?
							logging.error('%s: Terpene %s matches multiple patterns (at list index %d).', raw_sample_file_name, terpene_name, i)
							skip_this_file = True
						else:
							logging.debug('%s: Regex matched first time: "%s".', raw_sample_file_name, terpene_regex.pattern)
							regex_matched = True
						if terpene_name in terpenes_data:
							# Multiple match same regex?
							logging.error('%s: Terpene %s already recorded (at list index %d).', raw_sample_file_name, terpene_name, i)
							skip_this_file = True
						else:
							terpenes_data[terpene_name] = terpene_amount

				if original_terpene_name is None:
					logging.warning('%s: Terpene empty at index %d.', raw_sample_file_name, i)
				elif not regex_matched:
					# Match none?
					logging.error('%s: Terpene did not match anything: %s (list index %d).', raw_sample_file_name, original_terpene_name, i)
			if terpenes_data == {}:
				logging.debug('%s: No terpenes were added (%d were found).', raw_sample_file_name, len(raw_terpenes_1))
		if args.force_terpenes and terpenes_data == {}:
			skip_this_file = True

		# 1 Test Data Terpenes Total
		terpene_total = None
		raw_terpene_total = get_single_value(
			tree=tree,
			xpath=xpath_terpenes_total,
			fallback='',
			fallback_file=logfile_terpenes_total_noneFound,
			fallback_data={'Filename':raw_sample_file_name}
		)
		terpene_amount_match = re_percentageValue.match(raw_terpene_total)
		if terpene_amount_match:
			try:
				terpene_total = normalize_number(
					numberstring=raw_terpene_total
				)
			except ValueError as e:
				logging.warning('%s: Terpene-Total number error: %s.', raw_sample_file_name, raw_terpene_total)
		else:
			logging.info('%s: Non-percentage terpene-total: %s.', raw_sample_file_name, raw_terpene_total)
			continue

		# 1 Test Data Cannabinoids
		raw_cannabinoids_1 = tree.xpath(xpath_cannabinoids_1)
		cannabinoid_data = {}
		# if len(raw_cannabinoids_1) > 0:
		# 	logging.warning('%s: Both cannabinoid queries match!', raw_sample_file_name)
		if 0 == len(raw_cannabinoids_1):
			logging.debug('%s: No potency.', raw_sample_file_name)
		else:
			for i, raw_cannabinoid in enumerate(raw_cannabinoids_1, 1):

				# AMOUNT
				raw_cannabinoid_amount = get_single_value(
					tree=raw_cannabinoid,
					xpath='td[2]/text()',
					fallback=''
				)
				cannabinoid_amount_match = re_percentageValue.match(raw_cannabinoid_amount)
				if cannabinoid_amount_match:
					try:
						cannabinoid_amount = normalize_number(
							numberstring=raw_cannabinoid_amount[cannabinoid_amount_match.start():cannabinoid_amount_match.end()]
						)
					except ValueError as e:
						logging.warning('%s: Cannabinoid number error: %s (at list index %d).', raw_sample_file_name, raw_cannabinoid_info, i)
						continue
				else:
					logging.info('%s: Non-percentage cannabinoid (at list index %d).', raw_sample_file_name, i)
					continue

				# NAME
				## TODO: we could do levenshtein- and typewriterdistance (en-US) here
				original_cannabinoid_name = get_single_value(
					tree=raw_cannabinoid,
					xpath='td[1]/text()',
					fallback=''
				)

				logging.debug('####################NEW CANNABINOID: %s #####################', original_cannabinoid_name)
				regex_matched = False
				for cannabinoid_name in cannabinoids.keys():
					cannabinoid_regex = cannabinoids[cannabinoid_name]
					logging.debug('%s: Trying Regex "%s".', raw_sample_file_name, cannabinoid_regex.pattern)
					cannabinoid_match = cannabinoid_regex.match(original_cannabinoid_name)
					if cannabinoid_match:
						logging.debug('%s: Cannabinoid matched Regex "%s".', original_cannabinoid_name, cannabinoid_regex.pattern)
						if regex_matched:
							# Match more than one regex?
							logging.error('%s: Cannabinoid matches multiple patterns: %s (at list index %d).', raw_sample_file_name, cannabinoid_name, i)
							skip_this_file = True
						else:
							logging.debug('%s: Regex matched first time: "%s".', raw_sample_file_name, cannabinoid_regex.pattern)
							regex_matched = True
						if cannabinoid_name in cannabinoid_data:
							# Multiple items match same regex
							logging.error('%s: Cannabinoid already recorded: %s (at list index %d).', raw_sample_file_name, cannabinoid_name, i)
							skip_this_file = True
						else:
							cannabinoid_data[cannabinoid_name] = cannabinoid_amount

				if original_cannabinoid_name is None:
					logging.warning('%s: Cannabinoid name empty (at list index %d).', raw_sample_file_name, i)
				elif not regex_matched:
					# Match none?
					logging.error('%s: Cannabinoid did not match anything: %s (at list index %d).', raw_sample_file_name, original_cannabinoid_name, i)
			if cannabinoid_data == {}:
				logging.debug('%s: No cannabinoids were added (%d were found).', raw_sample_file_name, len(raw_cannabinoids_1+raw_cannabinoids_2))
		if args.force_cannabinoids and cannabinoid_data == {}:
			skip_this_file = True

		# 2 Test Data THC Total
		thc_total = None
		raw_thc_total = get_single_value(
			tree=tree,
			xpath=xpath_thc_total,
			fallback='',
			fallback_file=logfile_thc_total_noneFound,
			fallback_data={'Filename':raw_sample_file_name}
		)
		thc_amount_match = re_percentageValue.match(raw_thc_total)
		if thc_amount_match:
			try:
				thc_total = normalize_number(
					numberstring=raw_thc_total
				)
			except ValueError as e:
				logging.warning('%s: THC-Total number error: %s.', raw_sample_file_name, raw_thc_total)
		else:
			logging.info('%s: THC-Total not percentage: %s.', raw_sample_file_name, raw_thc_total)

		# 3 Test Data CBD Total
		cbd_total = None
		raw_cbd_total = get_single_value(
			tree=tree,
			xpath=xpath_cbd_total,
			fallback='',
			fallback_file=logfile_cbd_total_noneFound,
			fallback_data={'Filename':raw_sample_file_name}
		)
		cbd_amount_match = re_percentageValue.match(raw_cbd_total)
		if cbd_amount_match:
			try:
				cbd_total = normalize_number(
					numberstring=raw_cbd_total
				)
			except ValueError as e:
				logging.warning('%s: CBD-Total number error: %s.', raw_sample_file_name, raw_cbd_total)
		else:
			logging.info('%s: CBD-Total not percentage: %s.', raw_sample_file_name, raw_cbd_total)

		# 2 Sample Type
		sample_type = None
		raw_sample_type = get_single_value(
			tree=tree,
			xpath=xpath_sample_type,
			fallback='',
			errlevel=logging.ERROR,
			errmsg='%s: Sample type was not found',
			errparams=[raw_sample_file_name]
		)
		if raw_sample_type:
			regex_matched = False
			for sampletype_name in sample_types.keys():
				sampletype_regex = sample_types[sampletype_name]
				logging.debug('%s: Trying Regex "%s".', raw_sample_file_name, sampletype_regex)
				sampletype_match = sampletype_regex.match(raw_sample_type)
				if sampletype_match:
					logging.debug('%s: Sample type matched Regex "%s".', raw_sample_type, sampletype_regex.pattern)
					if regex_matched:
						# Match more than one regex?
						logging.error('%s: Sample type Regex "%s" matched before (sample type is now %s).', raw_sample_file_name, sampletype_regex.pattern, sampletype_name)
						skip_this_file = True
					else:
						logging.debug('%s: Regex matched first time: "%s".', raw_sample_file_name, sampletype_regex.pattern)
						regex_matched = True
						sample_type = sampletype_name
		# if not os.path.exists(os.path.join(args.database, sample_type)):
		# 	os.makedirs(os.path.join(os.path.expanduser(args.database),sample_type), exist_ok=True)
		if not regex_matched:
			# Match none?
			logging.error('%s: Sample type "%s" did not match anything (Xpath was %s).', raw_sample_file_name, raw_sample_type, xpath_canonicalURL)

		# 3 Sample Name
		sample_name = get_single_value(
			tree=tree,
			xpath=xpath_sample_name,
			errlevel=logging.error,
			errmsg='%s: Sample name was not found',
			errparams=[raw_sample_file_name]
		)

		# 4 Sample Provider
		sample_provider = get_single_value(
			tree=tree,
			xpath=xpath_sample_provider,
			fallback=get_single_value(
				tree=tree,
				xpath=xpath_sample_provider_anon,
				fallback_file=logfile_provider_noneFound,
				fallback_data={'Filename':raw_sample_file_name}
			)
		)
		if sample_provider == 'Anonymous':
			sample_provider = None
		elif sample_provider is not None:
			if sample_provider not in providers:
				providers.append(sample_provider)
			sample_provider = str(providers.index(sample_provider) + 1)

		# 5 Test UID
		test_uid = None
		raw_test_uid = get_single_value(
			tree=tree,
			xpath=xpath_test_uid,
			fallback='',
			fallback_file=logfile_uid_noneFound,
			fallback_data={'Filename':raw_sample_file_name}
		)
		test_uid_match = re_test_uid.match(raw_test_uid)
		if test_uid_match:
			test_uid = test_uid_match.group('uid')

		# 6 Test Time
		test_time = None
		raw_test_time = get_single_value(
			tree=tree,
			xpath=xpath_time_tested,
			fallback=''
		)
		re_date_match = re_date.match(raw_test_time)
		if re_date_match:
			possible_dates = dateparser_search.search_dates(
				text=raw_test_time,
				languages=['en'],
				settings={'DATE_ORDER':'MDY','STRICT_PARSING':True}
			)
			if type(possible_dates) == list and len(possible_dates) == 1:
				test_time = possible_dates[0][1].date().isoformat()
			else:
				logging.warning('%s: Test date (%s) was not understood.', raw_sample_file_name, raw_test_time)
		else:
			logging.error('%s: No test date was found (%s).', raw_sample_file_name, raw_test_time)

		# 7 Receipt Time
		receipt_time = None
		raw_receipt_time = get_single_value(
			tree=tree,
			xpath=xpath_time_received,
			fallback=''
		)
		re_date_match = re_date.match(raw_receipt_time)
		if re_date_match:
			possible_dates = dateparser_search.search_dates(
				text=raw_receipt_time,
				languages=['en'],
				settings={'DATE_ORDER':'MDY','STRICT_PARSING':True}
			)
			if type(possible_dates) == list and len(possible_dates) == 1:
				receipt_time = possible_dates[0][1].date().isoformat()
			else:
				logging.warning('%s: Receipt date (%s) was not understood.', raw_sample_file_name, raw_receipt_time)
		else:
			logging.error('%s: No receipt date was found (%s).', raw_sample_file_name, raw_receipt_time)

		if terpenes_data == {} and cannabinoid_data == {}:
			skip_this_file = True

		sample_data = {
			'Test Result UID':test_uid,
			'Sample Name':sample_name,
			'Test Time':test_time,
			'Receipt Time':receipt_time,
			'Provider':sample_provider,
			'Terpene TOTAL':terpene_total,
			'THC TOTAL':thc_total,
			'CBD TOTAL':cbd_total,
			'Sample Type':sample_type
		}
		sample_data.update(terpenes_data)
		sample_data.update(cannabinoid_data)

		for sample_data_field in list(sample_data.keys()):
			remove_key = False
			if sample_data[sample_data_field] is None:
				remove_key = True
			if sample_data_field not in DATA_ROW_FIELDS:
				remove_key = True
			if remove_key:
				del sample_data[sample_data_field]
		if sample_data == {}:
			skip_this_file = True

		if not skip_this_file:
			if args.csv:
				write_to_csv(
					filepath=sample_database_CSVfile,
					fieldnames=DATA_ROW_FIELDS,
					data=sample_data
				)
			if args.json:
				with open(sample_database_JSONfile, "a", encoding="utf-8") as databases_file:
					if not is_first_sample:
						databases_file.write(',')
					json.dump(sample_data, databases_file, separators=(',', ':'), sort_keys=True)
					is_first_sample = False
	if args.json:
		with open(sample_database_JSONfile, "a", encoding="utf-8") as databases_file:
			databases_file.write(']')

logging.debug('Finished main loop.')

if args.json:
	with open(sample_database_JSONfile, "a", encoding="utf-8") as databases_file:
		databases_file.write('}}')

print('All files have been processed. Please check the contents of the log file {}. It lists pages regarding different errors.', args.log)
