from bs4 import BeautifulSoup
from selenium import webdriver
from JSONUtil import *
from scrape_helper import *
from Review import Review
from urllib.parse import urlparse
from scrape_handler import scrape_main

cochrane_base_url = "https://www.cochranelibrary.com"

def select_review_topic(driver):
    topic = input("Enter your topic to retrieve reviews on: ")
    soup = scrape_page(driver, "https://www.cochranelibrary.com/cdsr/reviews/topics")
    matches = get_tags_by_tag_type_containing_text(soup, "button", topic)

    found_tag = None

    if len(matches) == 1:
        found_tag = matches[0]
    elif len(matches) > 1:
        for match in matches:
            yn = input("did you mean '" + match.text + "'? (Y/N) ")
            if yn.lower() == "y":
                found_tag = match
                break

    if found_tag is None:
        print("Error: no topic found")
        exit(0)

    # get set topic title
    topic_title = found_tag.text
    # get link within button's parent
    search_href = found_tag.parent["href"]

    return topic_title, search_href


def get_all_topic_links(driver):
    soup = scrape_page(driver, "https://www.cochranelibrary.com/cdsr/reviews/topics")
    for element in soup.findAll(lambda tag: tag if ("aria-label" in tag.attrs) else False):
        element.extract()
    topic_buttons = Element("button", "class", "btn-link")
    matches = get_soup_tags_by_element_object(soup, topic_buttons)

    topic_links = {}

    for topic_link_tag in matches:
        # get set topic title
        topic_title = topic_link_tag.text
        # get link within button's parent
        try:
            search_href = topic_link_tag.parent["href"]
        except KeyError:
            continue

        topic_links[topic_title] = search_href

    return topic_links


def missing_data_check(review, fail_data):
    members = [(attr, getattr(review, attr)) for attr in dir(review) if
               not callable(getattr(review, attr)) and not attr.startswith("__")]
    missing_data = []
    for attribute, value in members:
        if not value:
            missing_data.append(attribute)
        elif isinstance(value, dict):
            for key, data in value.items():
                if not data:
                    missing_data.append(key)
                elif isinstance(data, dict):
                    for header, info in data.items():
                        if not info:
                            missing_data.append(header)
        try:
            if None in value:
                missing_data.append(attribute)
        except TypeError:
            pass
    if missing_data:
        fail_data["incomplete"][review.doi] = missing_data


def scrape_review_search(driver, initial_search_page, fail_data, titles_only=True):
    next_page_element_parent = Element("div", "class", "pagination-next-link")
    next_page_element = Element("a", None, None, next_page_element_parent, retrieve_attribute="href")

    review_link_parent = Element("h3", "class", "result-title")
    review_link_element = Element("a", "target", "_blank", review_link_parent)

    current_results_soup = scrape_page(driver, initial_search_page)
    next_page = next_page_element.scrape(current_results_soup)
    first = True
    last = False

    # print("initial next page link " + str(next_page))

    # elements needed to continue to next scrape from previous scrape attempts
    last_scrape = str(fail_data["next scrape"])

    review_number_parent_parent = Element("div", "class", "search-results-item-tools")
    review_number_parent = Element("div", None, None, review_number_parent_parent)
    review_number_element = Element("label", None, None, review_number_parent, True, None)

    all_titles = []

    results_num = Element("span", "class", "results-number").scrape(current_results_soup).strip()

    # outer loop of whilst "next" within "a" within "div" with "class" = "pagination-next-link"
    while next_page or first or last or len(all_titles) < int(results_num):
        first = False

        # list of links for this page (href of a within h3[@class=result-title])
        review_link_tags = get_soup_tags_by_element_object_with_parent(current_results_soup, review_link_element)

        all_titles.extend([tag.text for tag in review_link_tags])

        if not titles_only:
            # is the correct next scrape number on this page?
            review_numbers = review_number_element.scrape(current_results_soup)
            review_numbers = [num.strip() for num in review_numbers]

            print(last_scrape)
            print(review_numbers)

            if str(last_scrape) in review_numbers:
                print("FOUND THE RIGHT REVIEW TO SCRAPE!")
                start_scraping_from = review_numbers.index(str(last_scrape))
            else:
                start_scraping_from = len(review_link_tags)

            for i in range(start_scraping_from, len(review_link_tags)):
                review_url = cochrane_base_url + review_link_tags[i]["href"]

                review_soup = scrape_page(driver, review_url)
                review_soup = format_soup(review_soup)
                print("We're reviewing review at " + review_url)
                # get Review object from link
                review = scrape_review_page(driver, review_soup, fail_data)

                if review:
                    # save/append to JSON
                    create_json_or_append_object(fail_data["file title"], review)

                if review is not None:
                    # check for any missing data, if so add to fail_data
                    missing_data_check(review, fail_data)

                #
                # update fail_data for next scrape
                fail_data["next scrape"] += 1
                last_scrape = fail_data["next scrape"]
                print("next scrape " + str(fail_data["next scrape"]))

        # get next soup
        if next_page:
            current_results_soup = scrape_page_but_wait(driver, next_page,
                                                        [review_number_element, next_page_element_parent])

        # get page after
        next_page = next_page_element.scrape(current_results_soup)
        if last:
            break
        if not next_page:
            last = True

    save_titles(fail_data["file title"], all_titles)

    return True


def scrape_review_page(driver, review_soup, fail_data, nested=False):
    error_page_element = Element("div", "class", "error-page-main-content-wrapper")
    if error_page_element.scrape(review_soup):
        return None

    authors, doi, publish_date, title = scrape_meta_data(review_soup)

    if "2023" not in publish_date:
        return None

    abstract = scrape_review_abstract(review_soup)
    data = scrape_review_contents_into_subsections(review_soup)
    review = Review(doi, authors, publish_date, title, abstract, data)

    if not nested:
        # get review references page
        reference_link_parent = Element("li", "class", "cdsr-nav-link")
        reference_link_element = Element("a", None, None, reference_link_parent)
        references_href = cochrane_base_url + get_href_from_element_by_containing(review_soup, reference_link_element,
                                                                                  "references")
        references_soup = scrape_page(driver, references_href)

        # add review references
        references = scrape_review_references(references_soup)
        for ref_groups in references:
            review.add_reference_group(ref_groups["reference_type"], ref_groups["references"])

        scrape_reference_links(driver, references, fail_data)

    return review


def scrape_meta_data(review_soup):
    doi = None
    doi_parent = Element("div", "class", "doi-header")
    doi_element = Element("a", None, None, doi_parent)
    dois = get_soup_tags_by_element_object_with_parent(review_soup, doi_element)
    if dois:
        doi = dois[0].get_text()

    author_parent = Element("li", "class", "author")
    author_element = Element("a", None, None, author_parent)
    author_tags = get_soup_tags_by_element_object_with_parent(review_soup, author_element)
    authors = [author_tag.get_text() for author_tag in author_tags]
    publish_date, title = scrape_title_publish_date(review_soup)
    return authors, doi, publish_date, title


def scrape_title_publish_date(review_soup):
    publish_date = None
    publish_date_parent_parent = Element("div", "class", "publication-metadata-block")
    publish_date_parent = Element("p", None, None, publish_date_parent_parent)
    publish_date_element = Element("span", "class", "publish-date", publish_date_parent)
    publish_tags = get_soup_tags_by_element_object_with_parent(review_soup, publish_date_element)
    if publish_tags:
        publish_date = publish_tags[0].get_text()
        publish_date = publish_date.split(": ")[-1]

    title = None
    title_parent = Element("header", "class", "publication-header")
    title_element = Element("h1", "class", "publication-title", title_parent)
    title_tags = get_soup_tags_by_element_object_with_parent(review_soup, title_element)
    if title_tags:
        title = title_tags[0].get_text()
    return publish_date, title


def scrape_reference_links(driver, references, fail_data):
    # reference_domains = fail_data["reference host domains"]

    # go through each references links and scrape additional information
    for ref_type in references:
        for ref_chunk in ref_type["references"]:
            for ref in ref_chunk["studies"]:
                try:
                    # print(ref)
                    if "links" in ref:
                        links = ref["links"]
                        full_scrape_success = False
                        if "Link to article" in links:
                            # for dev purposes only
                            soup, url = scrape_page_with_real_url(driver, links["Link to article"])
                            # update_domain_record(reference_domains, url)
                            full_scrape_success = scrape_link_to_article(driver, soup, url, ref, fail_data)
                        if "CENTRAL" in links and not full_scrape_success:
                            central_soup = scrape_page(driver, links["CENTRAL"])
                            scrape_central(central_soup, ref)
                        elif "PubMed" in links and not full_scrape_success:
                            pubmed_soup = scrape_page(driver, links["PubMed"])
                            scrape_pubmed(pubmed_soup, ref)
                except Exception as e:
                    print("EXCEPTION DURING REFERENCE SCRAPE: ")
                    message = ""
                    if "content" in ref:
                        message += "Failed to scrape link for reference: " + ref["content"]
                    if "links" in ref:
                        message += "\nscrape fail links: " + ref["links"]
                    print(message)
    # fail_data["reference host domains"] = reference_domains


def update_domain_record(reference_domains, url):
    if urlparse(url).netloc in reference_domains:
        reference_domains[urlparse(url).netloc] += 1
    else:
        reference_domains[urlparse(url).netloc] = 1


def scrape_link_to_article(driver, soup, url, reference_dict, fail_data):
    ref_review = None
    if str(urlparse(url).netloc) == "www.cochranelibrary.com":
        ref_review = scrape_review_page(driver, soup, fail_data, True)
        if ref_review:
            ref_review.add_to_existing(reference_dict)
    elif str(urlparse(url).netloc) == "www.sciencedirect.com":
        ref_review = scrape_science_direct(soup)
        if ref_review:
            ref_review.add_to_existing(reference_dict)
    elif str(urlparse(url).netloc) == "onlinelibrary.wiley.com":
        ref_review = scrape_wiley_online_library(driver, url, soup)
        if ref_review:
            ref_review.add_to_existing(reference_dict)
    elif str(urlparse(url).netloc) == "ascopubs.org":
        ref_review = scrape_ascopubs(driver, soup)
        if ref_review:
            ref_review.add_to_existing(reference_dict)
    else:
        print("ARTICLE LINK UNSUPPORTED " + url)
    if ref_review is not None:
        print("scraped reference from: " + url)
        missing_data_check(ref_review, fail_data)
        return True
    return False


def scrape_review_abstract(review_soup):
    abstract = {}

    abstract_master = Element("div", "class", "full_abstract")
    abstract_part = Element("section", None, None, abstract_master)
    abstract_part_title = Element("h3", "class", "title", abstract_part)
    abstract_part_body = Element("p", None, None, abstract_part)

    abstract_section_titles = get_soup_tags_by_element_object_with_parent(review_soup, abstract_part_title)
    abstract_section_bodies = get_text_by_element_object_grouped_by_parent(review_soup, abstract_part_body)

    if len(abstract_section_titles) != len(abstract_section_bodies):
        print("SOMETHING IS WRONG WITH THE ABSTRACT THE TITLES AREN'T MATCHING THE BODIES!")
        print(abstract_section_titles)
        print(abstract_section_bodies)

    for i in range(len(abstract_section_titles)):
        abstract[abstract_section_titles[i].get_text().lower()] = abstract_section_bodies[i]

    return abstract


def scrape_review_contents(review_soup):
    contents = {}
    body_master = Element("article")
    body_headers = ["conclusions", "summaryOfFindings", "background", "objectives", "methods", "results", "discussion"]
    body_parts = [Element("section", None, None, Element("section", "class", header, body_master))
                  for header in body_headers]
    body = zip(body_headers, body_parts)

    for header, part in body:
        try:
            contents[header.lower()] = get_soup_tags_by_element_object_with_parent(review_soup, part)[0].get_text(
                separator=' ')
        except IndexError:
            print("This review has no " + header + " section in it's main body")

    return contents


def scrape_review_contents_into_subsections(review_soup):
    contents = {}
    body_master = Element("article")
    body_headers = ["conclusions", "summaryOfFindings", "background", "objectives", "methods", "results", "discussion"]
    body_parts = [Element("section", None, None, Element("section", "class", header, body_master))
                  for header in body_headers]
    body = zip(body_headers, body_parts)

    recurse_element = Element("section")
    tagger_elements = [Element("h1"), Element("h2"), Element("h3"), Element("h4"), Element("h5")]
    content_elements = [Element("p"), Element("ul")]

    for header, part in body:
        try:
            if header == "methods":
                contents[header.lower()] = RecursiveScrapeTagger(part, recurse_element, tagger_elements,
                                                                 content_elements).scrape(review_soup)
            else:
                contents[header.lower()] = get_soup_tags_by_element_object_with_parent(review_soup, part)[0].get_text(
                    separator=' ')
        except (NoSuchElementException, IndexError):
            print("This review has no " + header + " section in it's main body")

    return contents


def scrape_review_references(references_soup):
    references_soup = format_soup(references_soup)

    # elements
    reference_section_parent = Element("section", "id", "references")
    reference_section_master = Element("section", None, None, reference_section_parent)
    reference_section_header_buffer = Element("div", "class", "section-header", reference_section_master)
    reference_section_header = Element("h3", "class", "title", reference_section_header_buffer)

    reference_buffer = Element("div", "class", "bibliographies", reference_section_master)
    reference_chunk_title = Element("div", "class", "reference-title-banner", reference_buffer)

    reference_master = Element("div", "class", "bibliography-section", reference_buffer)
    reference_element = Element("div", None, None, reference_master)

    reference_title_element = Element("span", "class", "citation-title", reference_element)

    reference_link_parent = Element("ul", "class", "citation-link-group", reference_element)
    reference_link_master = Element("li", None, None, reference_link_parent)
    reference_link_elements = Element("a", "class", "citation-link", reference_link_master, True, "href")

    # scrape structures

    reference_format = {
        "meta": {
            "title": reference_title_element
        },
        "content": reference_element,
        "links": ElementDict(reference_link_elements, None, "href", cochrane_base_url)
    }

    reference_structure = ScrapeStructure(reference_master, reference_format)

    chunk_format = {
        "id": reference_chunk_title,
        "studies": reference_structure
    }

    chunk_structure = ScrapeStructure(reference_buffer, chunk_format)

    type_format = {
        "reference_type": reference_section_header,
        "references": chunk_structure
    }

    reference_type_structure = ScrapeStructure(reference_section_master, type_format)

    references = reference_type_structure.scrape(references_soup)

    return references


def scrape_central(central_soup, reference):
    title_element = Element("h1", "class", "publication-title")
    abstract_element = Element("div", "id", "abstract")
    authors_element = Element("div", "class", "authors")
    added_element = Element("span", "class", "central-date-added")
    for element in central_soup.findAll('h2'):
        element.extract()

    abstract_div = get_soup_tags_by_element_object_with_parent(central_soup, abstract_element)
    if abstract_div:
        abstract_div = abstract_div[0]
        abstract_parts = abstract_div.findAll("p")
        # print(abstract_parts)
        try:
            abstract = {}
            for abstract_part in abstract_parts:
                abstract_section = abstract_part.get_text(separator=' ')
                abstract_section_title = re.match(r"^[A-Za-z/ ]*: ", abstract_section)[0]
                abstract[abstract_section_title] = abstract_section[len(abstract_section_title):]
            reference["abstract"] = abstract
        except (IndexError, TypeError):
            reference["abstract"] = abstract_div.get_text(separator=' ')

    scrape_element_add_to_meta(central_soup, reference, authors_element, "authors", split_authors)

    scrape_element_add_to_meta(central_soup, reference, title_element, "title")

    scrape_element_add_to_meta(central_soup, reference, added_element, "publish_date")


def scrape_element_add_to_meta(soup, reference, element, name, func=None):
    scrape = element.scrape(soup)
    if scrape:
        if func:
            scrape = func(scrape)
        if "meta" in reference:
            reference["meta"][name] = scrape
        else:
            reference["meta"] = {}
            reference["meta"][name] = scrape


def split_authors(authors):
    return authors.split(', ')


def scrape_pubmed(pubmed_soup, reference):
    # remove div.short-view (filled with duplicate content)
    short_view = get_soup_tags_by_element_object_with_parent(pubmed_soup, Element("div", "class", "short-view"))
    for element in short_view:
        element.extract()

    abstract_parent = Element("div", "id", "enc-abstract")
    abstract_element = Element("p", None, None, abstract_parent)
    subtitle_element = Element("strong", "class", "sub-title", abstract_element)

    if subtitle_element.scrape(pubmed_soup):
        abstract_parts = get_soup_tags_by_element_object_with_parent(pubmed_soup, abstract_element)
        try:
            abstract = dict(
                [(part.findAll("strong")[0].extract(), part.get_text(separator=' ')) for part in abstract_parts])
        except IndexError:
            abstract = abstract_element.scrape(pubmed_soup)
    else:
        abstract = abstract_element.scrape(pubmed_soup)

    pubmed_soup["abstract"] = abstract

    authors_element = Element("span", "class", "authors-list-item", Element("div", "class", "authors-list"), True, None)
    scrape_element_add_to_meta(pubmed_soup, reference, authors_element, "authors")

    # get h1.heading-title as title
    title_element = Element("h1", "class", "heading-title")
    scrape_element_add_to_meta(pubmed_soup, reference, title_element, "title")

    return abstract_element.scrape(pubmed_soup)


def scrape_science_direct(scidir_soup):
    for element in scidir_soup.findAll(lambda tag: tag if ("aria-hidden" in tag.attrs) else False):
        element.extract()

    doi = Element("a", "class", "doi").scrape(scidir_soup)

    authors_master = Element("a", "class", "author")
    authors_buffer = Element("span", "class", "content", authors_master)
    authors_parts = Element("span", "class", "text", authors_buffer, None, True)

    authors_in_bits = ScrapeStructure(authors_master, {"author_bits": authors_parts}).scrape(scidir_soup)
    alpha_regex = re.compile(r'[^a-zA-Z ]')
    authors = [alpha_regex.sub('', ' '.join(author["author_bits"])).strip() for author in authors_in_bits]

    citation_div = Element("div", None, None, Element("div", None, None, Element("div", "id", "publication")))
    try:
        full_container = get_soup_tags_by_element_object_with_parent(scidir_soup, citation_div)[0]
        full_container.findAll("a")[0].extract()
        publish_date = full_container.get_text(separator=' ').split(',')[1].strip()
    except IndexError:
        publish_date = citation_div.scrape(scidir_soup).strip()

    title = Element("span", "class", "title-text").scrape(scidir_soup)

    abstract_element = Element("div", "class", "abstract")
    abstract_part_master = Element("div", None, None, abstract_element)
    abstract_part_header = Element("h3", None, None, abstract_part_master)
    abstract_part_body = Element("p", None, None, abstract_part_master)

    abstract_parts = ScrapeStructure(abstract_part_master, {abstract_part_header: abstract_part_body}).scrape(
        scidir_soup)
    abstract = {header: body for part in abstract_parts for header, body in part.items()}
    if not abstract or None in abstract:
        abstract = abstract_element.scrape(scidir_soup)

    body_master = Element("div", "id", "body")
    body_parent = Element("div", None, None, body_master)
    body_section = Element("section", None, None, body_parent, None, True)
    sections = body_section.scrape(scidir_soup)
    if sections:
        body_header = Element("h2", None, None, body_section, None, True)

        content = {}
        headers = body_header.scrape(scidir_soup)

        for i in range(len(headers)):
            body_section = sections[i].replace(headers[i], '')
            content[headers[i].lower()] = body_section
    else:
        content = body_master.scrape(scidir_soup)

    # content = scrape_with_extract_as_key(scidir_soup, body_section, body_header)

    review = Review(doi, authors, publish_date, title, abstract, content)

    # print("sciencedirectscrape resulted in: ")
    # pprint.pprint(review.toJSON())

    return review


def scrape_wiley_online_library(driver, url, library_soup):
    format_soup(library_soup)
    doi_element = Element("a", "class", "epub-doi")
    doi = doi_element.scrape(library_soup)

    if not doi:
        library_soup = rescrape_but_wait_random(driver)
        doi = Element("a", "class", "epub-doi").scrape(library_soup)

    authors = Element("a", "class", "author-name", None, None, True).scrape(library_soup)

    title = Element("h1", "class", "citation__title").scrape(library_soup)

    publish_date = Element("span", "class", "epub-date").scrape(library_soup)

    abstract_parent = Element("section", "class", "article-section__abstract")
    abstract_element = Element("div", "class", "article-section__content", abstract_parent)
    abstract_part_master = Element("section", None, None, abstract_element)
    abstract_part_header = Element("h3", None, None, abstract_part_master)
    abstract_part_body = Element("p", None, None, abstract_part_master)

    abstract = scrape_header_body_under_master_or_default_to_element(library_soup, abstract_part_master,
                                                                     abstract_part_header, abstract_part_body,
                                                                     abstract_element)

    body = {}
    body_parent = Element("section", "class", "article-section__full")
    if body_parent.scrape(library_soup):
        body_part_master = Element("section", "class", "article-section__content", body_parent)
        body_part_header = Element("h2", None, None, body_part_master)
        body_part_content = Element("section", "class", "article-section__sub-content", body_part_master, None, True)
        body = scrape_header_body_under_master_or_default_to_element(library_soup, body_part_master, body_part_header,
                                                                     body_part_content, body_parent)
        if type(body) is dict:
            for section_name in body.keys():
                if type(body[section_name]) is list:
                    body[section_name] = ' '.join(body[section_name])

    review = Review(doi, authors, publish_date, title, abstract, body)

    # print("wiley online library resulted in: ")
    # pprint.pprint(review.toJSON())

    return review


def scrape_ascopubs(driver, asco_soup):
    asco_soup = rescrape_page_after_clicks(driver, asco_soup, Element("a", "id", "toggleAff"), ["show more"])

    format_soup(asco_soup)
    for element in asco_soup.findAll(lambda tag: tag.name == "select"):
        element.extract()

    title = Element("div", "class", "publicationContentTitle").scrape(asco_soup)

    author_parent = Element("span", "class", "NLM_contrib-group")
    author_buffer = Element("span", "class", "contribDegrees", author_parent)
    authors = Element("a", "class", "entryAuthor", author_buffer, None, True).scrape(asco_soup)

    publish_date = None
    publish_date_p = get_tags_by_tag_type_containing_text(asco_soup, "p", "Published online")
    if publish_date_p:
        publish_date = publish_date_p[0].get_text(separator=' ').replace("Published online", '')
        publish_date.strip()

    abstract_element = Element("div", "class", "abstractSection")
    # 2 styles of abstract: A and B
    abstract_section_master_A = Element("div", None, None, abstract_element)
    abstract_section_header_parent = Element("div", "class", "sectionInfo", abstract_section_master_A)
    abstract_section_header_A = Element("div", "class", "sectionHeading", abstract_section_header_parent)
    abstract_section_body_A = Element("p", None, None, abstract_section_master_A)

    if abstract_section_header_A.scrape(asco_soup):
        abstract = scrape_header_body_under_master_or_default_to_element(asco_soup, abstract_section_master_A,
                                                                         abstract_section_header_A,
                                                                         abstract_section_body_A,
                                                                         abstract_element)
    else:
        abstract_section_B = Element("p", None, None, abstract_element, None, True)
        abstract = {}
        sections = abstract_section_B.scrape_tags(asco_soup)

        for section in sections:
            bolds = section.findAll("b")
            if bolds:
                header = bolds[0].extract().get_text(separator=' ')
                body = section.get_text(separator=' ')
                abstract[header] = body

        if not abstract:
            abstract = abstract_element.scrape(asco_soup)

    body = None
    body_element = Element("div", "class", "hlFld-Fulltext")
    body_section_master = Element("div", "class", "NLM_sec_level_1", body_element)
    if body_section_master.scrape(asco_soup):
        body_section_title = Element("div", "class", "sectionInfo", body_section_master)
        body_section_bodies = Element("p", None, None, body_section_master, None, True)

        body = scrape_header_body_under_master_or_default_to_element(asco_soup, body_section_master, body_section_title,
                                                                     body_section_bodies, body_section_master)

        if type(body) is dict:
            for section_name in body.keys():
                body[section_name] = ' '.join(body[section_name])

    review = Review(None, authors, publish_date, title, abstract, body)

    # print("ascopub scrape resulted in: ")
    # pprint.pprint(review.toJSON())

    return review

if __name__ == '__main__':
    scrape_main(select_review_topic, scrape_review_search)  # Cochrane scraper call