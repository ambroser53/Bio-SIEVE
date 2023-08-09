from JSONUtil import *
import traceback
import undetected_chromedriver as uc

MAX_REPEAT_ATTEMPTS = 1

def colored(r, g, b, text):
    return "\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(r, g, b, text)


def code_clean_up(driver, topic_title, fail_data, cancelled):
    print("Saving fail_data")
    store_json("fail_data_" + topic_title_to_file_title(topic_title), fail_data)
    if cancelled:
       driver.close()


def scrape_main(search_director, top_level_scrape):
    chrome_options = uc.options.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")

    driver = uc.Chrome(chrome_options)
    # driver.minimize_window()

    topic_title, initial_search_page = search_director(driver)

    fail_data = get_fail_data(topic_title)

    cancelled = False
    failure_counter = 0

    while not cancelled:
        try:
            cancelled = top_level_scrape(driver, initial_search_page, fail_data)
        except KeyboardInterrupt:
            cancelled = True
        except Exception:

            print(colored(255, 0, 0, "EXCEPTION"))
            print(colored(255, 0, 0, traceback.print_exc()))
            exit(0)
            driver = uc.Chrome()
            driver.minimize_window()
            failure_counter += 1
            if failure_counter > MAX_REPEAT_ATTEMPTS:
                fail_data["next scrape"] += 1
                failure_counter = 0
        finally:
            code_clean_up(driver, topic_title, fail_data, cancelled)


# scrape_main(select_review_topic, scrape_review_search) # Cochrane scraper call
