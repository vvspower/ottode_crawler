import scrapy
import re
from manual_scraper_ext.items import Manual
import json


class OttodeSpider(scrapy.Spider):
    name = "ottode"
    allowed_domains = ["www.otto.de"]
    start_urls = ["http://www.otto.de/"]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.3,
        "CONCURRENT_REQUESTS": 5,
    }

    def parse(self, response, **kwargs):
        for link in response.css('a.nav_navi-elem::attr(href)').getall():
            if "/sale/" not in link and "/inspiration/" not in link:
                yield response.follow(response.urljoin(link),
                                      callback=self.parse_parent)

    def parse_parent(self, response, **kwargs):
        for a_tag in response.css('li.nav_local-link a.ts-link'):
            href = a_tag.css('::attr(href)').get()
            yield response.follow(href, callback=self.parse_product_page)

    def parse_product_page(self, response, **kwargs):
        for link in response.css('a.find_tile__productLink::attr(href)').getall():
            yield response.follow(link, callback=self.parse_product)

    def parse_product(self, response,  **kwargs):
        manual = Manual()
        for a_tag in response.css("ul.pdp_important-information__list a"):
            link = a_tag.css("::attr(href)").get()
            text = a_tag.xpath(".//text()[normalize-space()]").extract_first()
            if text:
                text = text.strip()
                if "Bedienungsanleitung" in text:
                    manual["file_urls"] = [link]

                    headline = response.css(
                        'h1.pdp_variation-name::text').get().replace('"', "").strip()
                    brand, model, product = self.clean_headline(
                        headline, response)
                    thumb = response.css(
                        'a.pl_sliding-carousel__slide::attr(href)').get()
                    #  removes product from product_parent
                    parent_product = response.css(
                        'ul.nav_grimm-breadcrumb li:nth-last-child(2) a::text').get()
                    manual['product_parent'] = parent_product
                    manual['brand'] = brand
                    manual['product'] = product
                    manual['model'] = model
                    manual['model_2'] = self.optimize_model(model)
                    manual["thumb"] = thumb
                    manual["url"] = response.url
                    manual["source"] = "otto.de"
                    manual["type"] = "Bedienungsanleitung"
                    manual["product_lang"] = "de"
                    script_tag = response.css(
                        'script[type="application/ld+json"]::text').get()
                    data = json.loads(script_tag)
                    gtin13 = data.get('gtin13')

                    manual['eans'] = gtin13

                    yield manual

    def clean_headline(self, headline, response):
        brand = ''
        script_tag = response.css(
            'script[type="application/ld+json"]::text').get()
        data = json.loads(script_tag)
        try:
            brand = data['brand']['name']
        except:
            brand = headline.split()[0]
            self.logger.error("Brand not present")
        product = response.css(
            'ul.nav_grimm-breadcrumb li:last-child a::text').get()

        model = self.clean_model(headline, brand, product)

        return brand, model, product

    def clean_model(self, headline, brand, product):
        model = ""
        if "»" in headline:
            try:
                model = re.search(
                    "(?:»(.*?)«|»(.*?)»|«(.*?)«)", headline).group(1)
            except:
                self.logger.error("Did not match")
        elif "," in headline:
            model = " ".join(headline.split(",")[0].split()[2:])
            if len(model) <= 1:
                model = headline.split(",")[1]

        try:
            if "»" in model:
                model = " ".join(model[model.index("»") + 1:].split())
            if "«" in model:
                model = " ".join(model[:model.index("«")].split())
        except:
            self.logger.error("Model empty")

        model = model.replace(",", "").replace("«", "").replace(
            "»", "").replace("(", "").replace(")", "")

        try:
            model = model.replace(brand, "").replace(product, "")
        except:
            self.logger.error("model is empty")

        if len(model.strip()) == 0:
            try:
                model = " ".join(headline.split()[2:])
                #  checks if model still empty then uses the product name
                if len(model.strip()) == 0:
                    model = " ".join(headline.split()[1:])
            except:
                self.logger.error("Not found")

        return model.replace("®", "").strip()

    def optimize_model(self, model):
        # checks if string contains number, likely to be a model number
        words = model.split()
        for word in words:
            if any(char.isdigit() for char in word):
                return word
        return ""
