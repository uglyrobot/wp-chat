import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from bs4 import BeautifulSoup


class WpdevdocsSpider(CrawlSpider):
    name = "wpdevdocs"
    allowed_domains = ["developer.wordpress.org"]
    start_urls = ["http://developer.wordpress.org/"]

    rules = (Rule(LinkExtractor(deny=r"reference/"), callback="parse_item", follow=True),)

    def parse_item(self, response):
        item = { 'text': '', 'info': {} }
        item['info']["url"] = response.url
        # get title from title tag
        item['info']["title"] = response.css("title::text").get()
        # get description from meta tag
        item['info']["description"] = response.css("meta[name=description]::attr(content)").get()
        # get text from div with id entry-content, convert html to text\
        html = response.css("#primary").get()
        if not html:
            html = response.css("#main").get()

        # if html
        if html:
            soup = BeautifulSoup(html, "html.parser")
            item['text'] = soup.get_text()
            return item

