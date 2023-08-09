import os
from typing import Dict

from scrape_handler import code_clean_up, scrape_main
from cochrane_scraper import *
from JSONUtil import *
import traceback
import sys
import undetected_chromedriver as uc
MAX_REPEAT_ATTEMPTS = 1


def get_most_common_article_sites(fail_data):
    domains = fail_data["reference host domains"]
    top_ten = sorted(domains, key=domains.get, reverse=True)[:10]
    print(top_ten)
    print(sum(domains.values()))
    # sciencedirect 12330
    # wiley 7271
    # ascopubs 3673
    # link.springer.com 3512
    # journals.lww.com 2884
    # academic.oup.com 2412
    # cochranelirary.com 1438
    # out of 48258
    exit(0)


def boot_driver(browser):
    chrome_options = uc.options.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")

    driver = uc.Chrome(chrome_options)
    return driver


def main(mode="", browser="chrome"):
    driver = boot_driver(browser)

    if mode == "1":
        topic_links = get_all_topic_links(driver)
        for topic_title, topic_search_link in topic_links.items():
            fail_data = get_fail_data(topic_title)
            if fail_data["finished"] == 1:
                print("Scrape already completed for " + topic_title)
                continue
            else:
                scrape_topic(driver, topic_search_link, topic_title, fail_data, browser)
    elif mode == "2":
        replace_all_title_pubdates(driver)
    elif mode == "3":
        rescrape_cochrane_contents(driver)
    else:
        topic_title, initial_search_page = select_review_topic(driver)

        fail_data = get_fail_data(topic_title)
        scrape_topic(driver, initial_search_page, topic_title, fail_data, browser)


def scrape_topic(driver, initial_search_page, topic_title, fail_data, browser):
    cancelled = False
    failure_counter = 0
    while not cancelled:
        try:
            cancelled = scrape_review_search(driver, initial_search_page, fail_data)
            if cancelled:
                print("All " + topic_title + " reviews have been scraped")
                fail_data["finished"] = 1
        except KeyboardInterrupt:
            cancelled = True
        except Exception as e:
            traceback.print_exc()
            driver = boot_driver(browser)
            failure_counter += 1
            if failure_counter > MAX_REPEAT_ATTEMPTS:
                fail_data["next scrape"] += 1
                failure_counter = 0
        finally:
            code_clean_up(driver, topic_title, fail_data, cancelled)



def rescrape_cochrane_contents(driver):
    recurse_element = Element("section")
    tagger_elements = [Element("h1"), Element("h2"), Element("h3"), Element("h4"), Element("h5")]
    content_elements = [Element("p"), Element("ul")]

    body_master = Element("article")
    part_master = Element("section", None, None, Element("section", "class", "methods", body_master))

    still_missing_data = ["cancer", "allergy_", "gynaecology", "consumer_", "dentistry", "developmental"]
    for file in os.listdir("./data"):
        if file.endswith(".json") and "fail_data" not in file \
                and any([(topic in file) for topic in still_missing_data]):
            print(file)
            with open("./data/" + file) as f:
                data = json.loads(f.read())
            for review in data:
                try:
                    soup = scrape_page(driver, review["id"])
                    review["data"]["methods"] = RecursiveScrapeTagger(part_master, recurse_element, tagger_elements,
                                                                      content_elements).scrape(soup)
                except Exception as e:
                    traceback.print_exc()
                    print("review error: could not rescrape page with attached doi: " + review["id"])
            with open('./data/' + file, 'w+') as outfile:
                json.dump(data, outfile, indent=4)

def replace_all_title_pubdates(driver):
    topic_titles = get_all_topic_links(driver).keys()

    for topic_title in topic_titles:
        file_title = topic_title_to_file_title(topic_title)
        if exists("./data/" + file_title + ".json"):
            with open("./data/" + file_title + ".json") as f:
                data = json.load(f)

            for review in data:
                soup = scrape_page(driver, review["id"])
                # replace top level publish_date and title
                publish_date, title = scrape_title_publish_date(soup)
                review['meta']['publish_date'] = publish_date
                review['meta']['title'] = title
                print("publish_date and  title updated at the bottom")

                for ref_type, ref_list in review['references'].items():
                    for study in ref_list:
                        for individual_ref in study["studies"]:
                            if "meta" in individual_ref:
                                if "The Cochrane Library" in individual_ref["meta"]["title"]:
                                    soup = scrape_page(driver, individual_ref["links"]["Link to article"])
                                    # replace top level publish_date and title
                                    publish_date, title = scrape_title_publish_date(soup)
                                    individual_ref['meta']['publish_date'] = publish_date
                                    individual_ref['meta']['title'] = title
                                    print("publish_date and  title updated at the top")
                            elif "title" in individual_ref:
                                if "The Cochrane Library" in individual_ref["title"]:
                                    soup = scrape_page(driver, individual_ref["id"])
                                    # replace top level publish_date and title
                                    publish_date, title = scrape_title_publish_date(soup)
                                    individual_ref['meta'] = {}
                                    individual_ref['meta']['publish_date'] = publish_date
                                    individual_ref['meta']['title'] = title
                                    print("publish_date and title updated at the top")

            with open("./data/" + file_title + ".json", 'w') as f:
                json.dump(data, f, indent=4)


def rescrape_director(driver):
    return "rescrape", None


def scrape_characteristics(soup, review_json):
    included_studies = []
    excluded_studies = []
    if "References to studies included in this review" in review_json["references"]:
        included_studies: List[Dict] = review_json["references"]["References to studies included in this review"]
    if "References to studies excluded from this review" in review_json["references"]:
        excluded_studies: List[Dict] = review_json["references"]["References to studies excluded from this review"]
    elif "References to studies included in this review" not in review_json["references"]:
        raise Exception("No included or excluded studies found")

    if included_studies:
        table_body = scrape_inclusion_characteristics(included_studies, soup)

    if excluded_studies:
        scrape_exclusion_characteristics(excluded_studies, soup)


def scrape_inclusion_characteristics(included_studies, soup):
    included_top = Element("section", "class", "characteristicIncludedStudiesContent")
    included_master = Element("div", "class", "table", included_top)
    included_study_heading = Element("div", "class", "table-heading", included_master)
    table_body = Element("tbody", None, None, Element("table"))
    inclusion_characteristics: list[dict[str, dict]] = ScrapeStructure(included_master, {
        included_study_heading: TableScraper(table_body)
    }).scrape(soup)
    # add collected new inclusion information to the reviews' json
    for char in inclusion_characteristics:
        study = next(iter(char))
        characteristics = char[study]
        for reference in included_studies:
            if study in reference["id"]:
                reference.update(characteristics)
    return table_body


def scrape_exclusion_characteristics(excluded_studies, soup):
    excluded_top = Element("section", "class", "characteristicsOfExcludedStudies")
    excluded_master = Element("div", "class", "table", excluded_top)
    table_body = Element("tbody", None, None, Element("table"))
    exclusion_characteristics = ScrapeStructure(excluded_master, {
        'excluded_characteristics': TableScraper(table_body)
    }).scrape(soup)
    if exclusion_characteristics:
        exclusion_characteristics = exclusion_characteristics[0]['excluded_characteristics']

        # add collected new exclusion information to the reviews' json
        for study, reason in exclusion_characteristics.items():
            for reference in excluded_studies:
                if study in reference["id"]:
                    reference["Exclusion Reason"] = reason


def rescrape_characteristics_from_ids(driver, noner, fail_data):
    for file in os.listdir("./cochrane_data"):
        if file.endswith(".json") and "fail_data" not in file and file not in fail_data['completed']:
            print(file)
            with open("./cochrane_data/" + file) as f:
                data = json.loads(f.read())

            for i in range(fail_data['next scrape'], len(data)):
                try:
                    real_url = get_real_url(driver, data[i]["id"])
                    soup = scrape_page(driver, real_url[:-4]+'references#characteristicStudies')
                    if get_tag_by_element_containing(soup, Element("h2", "class", "title"),
                                                     ["Characteristics of studies"]):
                        scrape_characteristics(soup, data[i])
                        fail_data["success"] += 1
                    else:
                        print("no characteristics on review with attached doi: " + data[i]['id'])
                        fail_data["fail"] += 1
                        fail_data["failures"][data[i]['id']] = "no characteristics on review"
                    fail_data["next scrape"] += 1
                except Exception as e:
                    traceback.print_exc()
                    print("review error: could not rescrape page with attached doi: " + data[i]['id'])
                    fail_data["fail"] += 1
                    fail_data["failures"][data[i]['id']] = str(e)

            with open("./cochrane_data/" + file, 'w') as f:
                json.dump(data, f, indent=4)
            fail_data["completed"].append(file)
            fail_data["next scrape"] = 0
    return True



if __name__ == "__main__":
    main("1")


