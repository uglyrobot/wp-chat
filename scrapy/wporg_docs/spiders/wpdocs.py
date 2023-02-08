import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from bs4 import BeautifulSoup


class WpdocsSpider(CrawlSpider):
    name = "wpdocs"
    allowed_domains = ["wordpress.org"]
    start_urls = ["https://wordpress.org/documentation/"]

    rules = (Rule(LinkExtractor(allow=r"documentation/"), callback="parse_item", follow=True),)

    def parse_item(self, response):
        item = { 'text': '', 'info': {} }
        item['info']["url"] = response.url
        # get title from title tag
        item['info']["title"] = response.css("title::text").get()
        # get description from meta tag
        item['info']["description"] = response.css("meta[name=description]::attr(content)").get()
        # get text from div with class entry-content, convert html to text
        html = response.css("div.entry-content").get()

        # if html and url starts with https://wordpress.org/documentation/article/ then:
        if html and response.url.startswith("https://wordpress.org/documentation/article/"):
            soup = BeautifulSoup(html, "html.parser")
            item['text'] = soup.get_text()
            return item
