import logging
import os
import json
import re
import datetime
from urllib.parse import urljoin

import requests
import PyRSS2Gen
from bs4 import BeautifulSoup
from ftfy import fix_encoding

TEST_URL = 'http://rendezvousavecmrx.free.fr/page/liste.php'


logger = logging.getLogger(__name__)
current_path = os.path.dirname(__file__)


def load_config():
    config = {}

    # load app configuration
    with open(os.path.join(current_path, 'config.json')) as conf_file:
        config_file = json.load(conf_file)

    # get environment variable otherwise use config file
    config['START_URL'] = os.getenv('START_URL', config_file['START_URL'])
    config['OUTPUT_FILE'] = os.getenv('OUTPUT_FILE', config_file['OUTPUT_FILE'])
    config['PROGRAM_TITLE'] = os.getenv('PROGRAM_TITLE', config_file['PROGRAM_TITLE'])
    config['PROGRAM_URL'] = os.getenv('PROGRAM_URL', config_file['PROGRAM_URL'])
    config['PROGRAM_DESC'] = os.getenv('PROGRAM_DESC', config_file['PROGRAM_DESC'])

    # check mandatory config parameters
    for value in config.values():
        if len(str(value)) == 0:
            raise Exception('Incorrect configuration for %s : %s' % value)

    return config


def get_programs(url):
    """
    List all the programs of the page.
    Designed for http://rendezvousavecmrx.free.fr/page/liste.php

    :param url: URL of the main page
    :return: list of dict {title, description, link, date}
    """

    # constants
    program_page = 'detail_emission.php'
    title_id = 'titre'
    program_id = 'emission'
    link_regex = re.compile('.*mp3$')

    content_main = requests.get(url)
    soup_main = BeautifulSoup(content_main.text, 'lxml')

    programs = []

    for page_link in soup_main.find_all('a'):
        page_url = urljoin(url, page_link.attrs['href'])

        if program_page in page_url:
            logger.info('Parsing %s' % page_url)

            content_page = requests.get(page_url)
            soup_page = BeautifulSoup(content_page.text, 'lxml')

            program = {
                'title': '',
                'description': '',
                'link': '',
                'date': None
            }

            # program title
            if len(soup_page.find_all('div', id=title_id)) > 0:
                program['title'] = fix_encoding(soup_page.find('div', id='titre').text)

            # program description
            if len(soup_page.find_all('div', id=program_id)) > 0:
                program['description'] = fix_encoding(soup_page.find('div', id='emission').text)

            # program link
            if len(soup_page.find_all('a', href=link_regex)) > 0:
                program['link'] = urljoin(page_url, soup_page.find('a', href=link_regex).attrs['href'])

            # do we have enough data for RSS ?
            if len(program['title']) == 0 or len(program['description']) == 0 or len(program['link']) == 0:
                logger.warning('Cannot find all data for %s (%s)' % (program['title'], page_url))
                continue

            # try to determine the date based on the filename, it should be YYYY-MM-DD
            date_pattern = '.*_(\d{4})_(\d{2})_(\d{2})\.mp3$'
            date_search = re.search(date_pattern, program['link'], re.IGNORECASE)
            if date_search:
                program['date'] = '-'.join(date_search.groups())
            else:
                logger.warning('Cannot determine date of %s (%s)' % (program['title'], page_url))

            programs.append(program)

    logger.info('%i programs fetched' % len(programs))

    # sort it by most recent date
    return sorted(programs, key=lambda p: p['date'], reverse=True)


def build_rss_feed(title, link, description, items, filename):
    """
    Generates a local XML file (RSS compliant)

    :param title: Title of the feed
    :param link: URL of the feed
    :param description: Description of the feed
    :param items: list of items to be included in the feed
    :param filename: output filename
    """
    rss_items = []

    for item in items:
        item_date = datetime.datetime.strptime(item['date'], '%Y-%m-%d')

        rss_item = PyRSS2Gen.RSSItem(
                title=item['title'],
                link=item['link'],
                description=item['description'],
                guid=PyRSS2Gen.Guid(item['link']),
                pubDate=item_date
        )

        rss_items.append(rss_item)

    rss = PyRSS2Gen.RSS2(
        title=title,
        link=link,
        description=description,
        lastBuildDate=datetime.datetime.now(),
        items=rss_items)

    rss.write_xml(open(filename, "w"))


def main():
    try:
        config = load_config()
        program_list = get_programs(config['START_URL'])
        build_rss_feed(config['PROGRAM_TITLE'], config['PROGRAM_URL'], config['PROGRAM_DESC'], program_list,
                       config['OUTPUT_FILE'])
    except Exception as e:
        logger.critical('Error occurred during process : %s' % str(e))


if __name__ == '__main__':
    log_format = '%(asctime)s  %(levelname)-20s %(name)-15s %(message)s'
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'), format=log_format)
    main()
