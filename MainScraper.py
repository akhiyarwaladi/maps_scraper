from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from parsel import Selector
from sqlalchemy import event,create_engine,types
import re
import time
import sys
from PlacesVisualiser import *

googleAcceptButtonClicked = False

# setUpWebDriver
options = webdriver.ChromeOptions()
#options.add_argument('headless')  # Make browser open in background
options.add_argument('--start-maximized')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
# driver = webdriver.Chrome(ChromeDriverManager().install())

def check_exists_by_xpath(xpath):
    """
    This function checks if the element specified by the xpath is present at the website.
    It is used to check if any places are available in the Google Maps searching results' menu.

    :param xpath: the xpath of searched element
    :return: boolean value corresponding to the existence of the searched element
    """
    try:
        driver.find_element(By.XPATH, xpath)
    except NoSuchElementException:
        return False
    return True


def scrollDownLeftMenuOnGoogleMaps(counter, waitingTime):
    """
    This function is responsible for scrolling down the menu visible at the left.
    It is used while searching for places at Google Maps. It allows seeing more places relevant for the search value.

    :param counter: number of scrolls down
    :param waitingTime: waiting time until next scroll (new results are loaded)
    """
    menu_xpath = '/html/body/div[3]/div[9]/div[9]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]/div[3]/div/a'

    if check_exists_by_xpath(menu_xpath):
        for i in range(counter):
            wait = WebDriverWait(driver, waitingTime)
            menu_left = wait.until(EC.visibility_of_element_located((By.XPATH, menu_xpath)))
            menu_left.send_keys(Keys.SPACE)


def searchForPlace(url, typeOfPlace):
    """
    This function is responsible for searching a place of specific type at specific location with set zoom.
    All information about searching are contained in the URL.

    :param url: path which is inserted into browser
    :param typeOfPlace: type of place searched in Google Maps
    :return: dictionary containing places found using this URL
    """
    global googleAcceptButtonClicked
    driver.get(url)

    # only at the first page click the "accept all" ("zaakceptuj wszystko") button
    #if not googleAcceptButtonClicked:
        #print('Clicked')
        #clickAcceptAllButton()

    # scroll down left menu
    scrollDownLeftMenuOnGoogleMaps(counter=4, waitingTime=2)

    # get the source code of the page
    page_content = driver.page_source
    response = Selector(page_content)

    placesResults = []
    # save the search results into a dictionary
    for el in response.xpath('//div[contains(@aria-label, "Hasil untuk")]/div/div[./a]'):
        placesResults.append({
            'link': el.xpath('./a/@href').extract_first(''),
            'title': el.xpath('./a/@aria-label').extract_first(''),
            'type': typeOfPlace
        })

    print(placesResults)
    return placesResults


def clickAcceptAllButton():
    """
    This function is responsible for clicking "accept all" button at the first page opened after initialization of
    the webdriver.
    """
    global googleAcceptButtonClicked
    button_path = '//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[1]/div[3]/div[1]/div[1]/form[2]/div/div/button'
    wait = WebDriverWait(driver, 1)
    button = wait.until(EC.visibility_of_element_located((By.XPATH, button_path)))
    button.click()
    googleAcceptButtonClicked = True


def addLonLatToDataFrame(df):
    """
    This function adds columns "lat" (latitude) and "lon" (longitude) to dataframe containing list of found places.

    :param df: dataframe containing list of found places
    :return: dataframe contatining list of found places and each place has assigned latitude and longitude
    """
    lat = []
    lon = []
    for index, row in df.iterrows():
        link = df.at[index, 'link']
        # print(link, "\n")
        latLon = re.search('!3d(.*)!16', link).group(1).split('!4d')
        # print(latLon[0], latLon[0])
        lat.append(latLon[0])
        lon.append(latLon[1])

    df['lat'] = lat
    df['lon'] = lon

    df = df[['lat', 'lon', 'type', 'title', 'link']]  # set order of columns

    return df


def closeDriver():
    """
    This function quits the driver. Driver is created at the beginning of MainScrapper file.
    """
    driver.quit()


def generateUrls(typeOfPlace):
    """
    This function generated urls which are used during searching for places of specific type.

    :param typeOfPlace: type of place searched in Google Maps
    :return: list of generated URLs containing type of place, searched location, and zoom of searching
    """
    pointsDirectory = "generatedPoints/"
    points_df = pd.read_csv(pointsDirectory + "Points_alfamart.csv", index_col=False)

    base = 'https://www.google.com/maps/search/'

    generated_urls = []
    generated_store = []

    for index, row in points_df.iterrows():
        point_lat = points_df.at[index, 'lat']
        point_lon = points_df.at[index, 'lon']
        point_store = points_df.at[index, 'store']
        zoom = 16
        url = base
        url += str(typeOfPlace) + '/@'
        url += str(point_lat) + ',' + str(point_lon) + ',' + str(zoom) + 'z'
        generated_urls.append(url)
        generated_store.append(point_store)
    return generated_urls,generated_store


def insert_alfabi_temp(name_temp, df_insert, if_exists="append"):
    try:

        
        engine_stmt = "oracle://%s:%s@%s/%s" % ( 
            'report', 
            'justd0it',
            '10.234.152.61',
            'alfabi' 
        )


        engine = create_engine(engine_stmt)


        dtype = {
            c:types.VARCHAR(df_insert[c].str.len().max()) 
            for c in df_insert.columns[df_insert.dtypes == 'object'].tolist()
        }
        df_insert.to_sql(
            name=name_temp, 
            con=engine, 
            index=False, 
            if_exists=if_exists,
            dtype=dtype
        )

        print('done inserting {} data'.format(df_insert.shape[0]))

        engine.dispose()
        return 0

    except Exception as e:
        print('Exception {}'.format(e))
        return e



if __name__ == "__main__":

    start = time.time()

    # check if any types are specified in the arguments
    types_of_places = sys.argv[1:]

    if len(types_of_places) == 0:
        types_of_places = ['indomaret']  # set the types of searched places

    print(types_of_places)
    for typeOfPlace in types_of_places:

        urls,store = generateUrls(typeOfPlace)

        print("total number of points to check:" + str(len(urls)))

        list_of_places = []
        progressCounter = 0
        for idx, url in enumerate(urls):
            new_places = searchForPlace(url, typeOfPlace)
            list_of_places += new_places  # concat two lists
            progressCounter += 1
            print("progress: " + str(round(100 * progressCounter / len(urls), 2)) + "%")
            

            df = pd.DataFrame(list_of_places)
            # df.to_csv('database/' + typeOfPlace + '_v0.csv', index=False)
            df = df.drop_duplicates()
            df = addLonLatToDataFrame(df)

            df['store'] = store[idx]
            df = df.astype(str)

            print("number of places:" + str(df.shape[0]))

            insert_alfabi_temp(
                'alfagift_store_competitor',
                df,
                if_exists='replace'
            )

            #df.to_csv('database/' + typeOfPlace + '_v1.csv', index=False)
            #break

    closeDriver()

    end = time.time()
    print("total time:" + str(end - start) + " seconds --> " + str((end - start) / 60) + " minutes")
