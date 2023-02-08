import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from bs4 import BeautifulSoup


class WpdevcodeSpider(CrawlSpider):
    name = "wpdevcode"
    allowed_domains = ["developer.wordpress.org"]
    start_urls = [
        "https://developer.wordpress.org/reference/functions/",
        "https://developer.wordpress.org/reference/hooks/",
        "https://developer.wordpress.org/reference/classes/",
        "https://developer.wordpress.org/reference/methods/",
        ]

    rules = (Rule(LinkExtractor(allow=r"reference/", deny=r"reference/files/"), callback="parse_item", follow=True),)

    def parse_item(self, response):
        item = { 'text': '', 'info': {} }
        item['info']["url"] = response.url
        # get title from title tag
        item['info']["title"] = response.css("title::text").get()
        # get description from meta tag
        item['info']["description"] = response.css("meta[name=description]::attr(content)").get()
        # get text from div with class entry-content, convert html to text
        html = response.css("#main").get()

        # if html and url does not contain /page/ then:
        if html and response.url.find("/page/") == -1:
            soup = BeautifulSoup(html, "html.parser")
            item['text'] = soup.get_text()
            return item