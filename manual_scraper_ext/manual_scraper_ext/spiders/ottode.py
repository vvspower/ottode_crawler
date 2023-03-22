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
                # print(link)
                yield response.follow(response.urljoin(link),
                                      callback=self.parse_parent)

    def parse_parent(self, response, **kwargs):
        for a_tag in response.css('li.nav_local-link a.ts-link'):
            href = a_tag.css('::attr(href)').get()
            parent_product = a_tag.css('::text').get()
            yield response.follow(href, callback=self.parse_product_page, meta={
                'parent_product': parent_product})

    def parse_product_page(self, response, **kwargs):
        parent_product = response.meta["parent_product"]
        for link in response.css('a.find_tile__productLink::attr(href)').getall():
            yield response.follow(link, callback=self.parse_product, meta={
                'parent_product': parent_product})

    def parse_product(self, response,  **kwargs):
        manual = Manual()
        parent_product = response.meta["parent_product"]
        headline = response.css(
            'h1.pdp_variation-name::text').get().replace('"', "").strip()
        brand, model, product = self.clean_headline(headline)
        print(f"Brand: {brand}, Model: {model}, Product: {product}")
        thumb = response.css('a.pl_sliding-carousel__slide::attr(href)').get()
        manual['product_parent'] = parent_product
        manual['brand'] = brand
        manual['product'] = product
        manual['model'] = model
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

        for a_tag in response.css("ul.pdp_important-information__list a"):
            link = a_tag.css("::attr(href)").get()
            text = a_tag.xpath(".//text()[normalize-space()]").extract_first()
            if text:
                text = text.strip()
                if "Bedienungsanleitung" in text:
                    manual["file_urls"] = [link]
                    yield manual

    def clean_headline(self, headline):
        if "»" in headline:
            brand, model, product = self.case_1(headline)
        else:
            brand, model, product = self.case_2(headline)
        if len(model) == 0:
            try:
                model = headline.split()[2].strip(",").strip(
                    "«").strip("»").strip("(").strip(")")
            except:
                model = headline.split()[1].strip(",").strip(
                    "«").strip("»").strip("(").strip(")")

        return brand, model, product

    def case_1(self, headline):
        seperated = headline.split('»')
        model = re.search('»(.+?)«', headline).group(1)
        if len(seperated[0].split()) > 3:
            brand = seperated[0].split()[0] + " " + seperated[0].split()[1]
            product = seperated[0].split()[2] + " " + seperated[0].split()[3]
        else:
            brand = headline.split()[0]
            product = headline.split()[1]
        if len(headline.split("»")[0].split()) < 2:
            product = headline.split("»")[1]

        return brand.strip(",").strip("«").strip("»").strip("(").strip(")"), model.strip(",").strip("«").strip("»").strip("(").strip(")"), product.strip(",").strip("«").strip("»").strip("(").strip(")")

    def case_2(self, headline):
        brand = headline.split()[0].strip(",")
        product = headline.split()[1].strip(",")
        model = " ".join(headline.split(",")[0].split()[2:])
        if "+" in headline:
            brand = headline.split()[0] + \
                headline.split()[1] + headline.split()[2]
            product = headline.split()[3]
        return brand.strip(",").strip("«").strip("»").strip("(").strip(")"), model.strip(",").strip("«").strip("»").strip("(").strip(")"), product.strip(",").strip("«").strip("»").strip("(").strip(")")
