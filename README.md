# Python Web Scraper

## Overview

This project is a Python-based web scraper that collects the latest news articles from the **Inshorts platform**. The scraper extracts key information such as headlines, summaries, authors, publish dates and article images. The collected data is stored in a structured JSON file and images are downloaded locally. This project demonstrates skills in web scraping, API handling, data cleaning and automation using Python.

## Features

* Scrapes multiple news categories from Inshorts.
* Extracts structured information including - 
  * Headline.
  * Summary.
  * Author.
  * Publish Date.
  * Source Link.
  * Image URL.
* Downloads article images.
* Removes duplicate news entries.
* Saves cleaned data to a JSON file.

## Project Structure

```
├── Scraper.py           # Main scraping script
├── requirements.txt      # Python dependencies
├── images/               # Downloaded article images
├── news_data.json        # Scraped news dataset
```

## Requirements

Install the required dependencies -
```
pip install -r requirements.txt
```

## How to Run the Project (Local Machine)

1. Clone or download the project.
2. Open the project folder in terminal.
3. Install dependencies - 
```
pip install -r requirements.txt
```

4. Run the scraper - 
```
python Scraper.py
```

5. Output files will be generated - 

   * `news_data.json`
   * `images/` folder containing downloaded images.

## How to Run in Google Colab

1. Upload the project zip file to Colab.
2. Unzip the project -
```
!unzip "Python Web Scraper.zip"
```
3. Install dependencies - 
```
!pip install -r requirements.txt
```
4. Run the scraper - 
```
!python Scraper.py
```

5. Download the output files if needed.

## Challenges Faced

1. Handling Dynamic Content - Inshorts loads additional news dynamically. To address this, multiple API requests were handled to fetch more articles.
2. Duplicate News Entries - Some articles appeared multiple times across categories. A filtering mechanism was implemented to remove duplicate entries.
3. Image Download Handling - Not all articles contained valid image URLs. Exception handling was added to prevent the script from crashing.
4. Request Limitations - Frequent requests to the API could potentially cause rate limiting. To mitigate this, request frequency was controlled and pagination limits were adjusted.

## Future Improvements

* Store scraped data in a database (SQLite/PostgreSQL).
* Build a dashboard for news visualization.
* Implement news sentiment analysis using NLP.
* Automate the scraper with scheduled jobs.
