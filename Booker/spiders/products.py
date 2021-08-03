import scrapy
from urllib.parse import parse_qs, quote, urlsplit

CUST_NO = 725936088
EMAIL = 'jonathan.hastings@costcutter.com'
PASS = 'Ebor,123'

def get_description(lines):
    description = ''
    for line in lines:
        description += line.strip()
    description = description.replace('\n',' ').replace('Show less...','')
    description = ' '.join(description.split())
    description = description if description else 'N/A'
    return description

class ProductsSpider(scrapy.Spider):
    name = 'products'
    allowed_domains = ['www.booker.co.uk']

    def start_requests(self):
        formdata = {
                        'ReturnUrl':'',
                        'uid':'9265a4ca-929d-44b8-96bc-a6d354033f60',
                        'CustomerNumber':'725936088',
                        'Email':'jonathan.hastings@costcutter.com',
                        'Password':'Ebor,123'
                    }
        yield scrapy.FormRequest('https://www.booker.co.uk/login', formdata=formdata, callback=self.parse)

    def parse(self, response):
        yield scrapy.Request('https://www.booker.co.uk/products/categories', callback=self.parse_category)

    def parse_category(self, response):
        if 'Website%20Bulletin' in response.url:
            formdata = {
                            'ContinueUrl' : response.xpath('//input[@id="ContinueUrl"]/@value').get(),
                            'Content' : response.xpath('//input[@id="Content"]/@value').get(),
                            'uid' : response.xpath('//input[@id="uid"]/@value').get(),
                            'IsRead' : 'true'
                        }
            yield scrapy.FormRequest('https://www.booker.co.uk/Website%20Bulletin', dont_filter=True, formdata=formdata, callback=self.parse_category)
        else:
            categories = response.xpath('//a[@class="departmentItemx "]/@href').getall()

            formdata = {
                        'ReturnUrl':'',
                        'uid':'9265a4ca-929d-44b8-96bc-a6d354033f60',
                        'CustomerNumber':'725936088',
                        'Email':'jonathan.hastings@costcutter.com',
                        'Password':'Ebor,123'
                    }
       
            ########### Limit Categories here ###########
            for i, cateogry in enumerate(categories):
                parsed = urlsplit(cateogry)
                query_dict = parse_qs(parsed.query)
                categoryName = query_dict['categoryName'][0]
                return_url = quote(cateogry)
                url = f'https://www.booker.co.uk/products/print-product-list-ungroup?printType=ProductList&categoryName={categoryName}&pr=%7BminPrice%3A0%2CmaxPrice%3A0%7D'
                
                login = 'https://www.booker.co.uk/login'
                yield scrapy.FormRequest(login,formdata=formdata,meta={'Referer':cateogry, 'URL':url, 'cookiejar': i}, callback=self.login_again, dont_filter=True)

    def login_again(self, response):
        meta = {'Referer': response.meta['Referer'] , 'URL':response.meta['URL'], 'cookiejar': response.meta['cookiejar']}
        yield response.follow(response.meta['Referer'], callback=self.to_print_list, meta=meta)

    def to_print_list(self, response):
        meta = {'Referer': response.meta['Referer'] , 'URL':response.meta['URL'], 'cookiejar': response.meta['cookiejar']}
        yield response.follow(response.meta['URL'], meta=meta, callback=self.parse_print_list)

    def parse_print_list(self, response):
        rows = response.xpath('//table[@class="table-desktop"]/tbody/tr')
        prs = {}
        for row in rows:
            barcode = row.xpath('.//td/*[@class="barcode"]/@jsbarcode-value').get()
            pro_code = int(row.xpath('.//td[not(@id) and not(@class)]/text()').get())
            pack_format = row.xpath('.//td[@id="packsize"]/text()').get()
            tds = row.xpath('.//td[contains(@class,"text-right")]/text()').getall()
            wholesale = tds[1]
            vat = tds[3]
            barcode = barcode + '\t' if barcode else 'N/A'
            prs[pro_code] = {
                'Barcode' : barcode,
                'Product ID' : pro_code,
                'Wholesale Price' : wholesale,
                'Packet Format' : pack_format,
                'Vat' : vat
            }
       
        meta={'Products':prs, 'cookiejar': response.meta['cookiejar']}
        yield response.follow(response.meta['Referer'], meta=meta, callback=self.parse_product_list, dont_filter=True)

    def parse_product_list(self, response):
        meta={'Products':response.meta['Products'], 'cookiejar': response.meta['cookiejar']}
        products = response.xpath('//div[contains(@class,"product-image")]/a/@href').getall()
        for product in products:
            yield response.follow(product, meta=meta, callback=self.parse_product)
        
        next = response.xpath('//a[@rel="next"]/@href').get()
        if next:
            yield response.follow(next, meta=meta, callback=self.parse_product_list)
        
    def parse_product(self, response):
        name = response.xpath('//h4[@class="d-inline pr-2 font-weight-bold"]/text()').get().strip()
        id_ = int(response.xpath('//h4[contains(@class,"product-id")]/text()').get().strip())
        description = get_description(response.xpath('//div[@id="product-details-show-more"]/p/text()').getall())
        promo_price = response.xpath('//span[@class="discount font-weight-bold"]/text()').get()
        if promo_price:
            on_promo = 'Yes'
        else:
            promo_price = 'N/A'
            on_promo = 'No'
  
        product = response.meta['Products'][id_]
        yield {
            'Barcode' : product['Barcode'],
            'Product ID' : id_,
            'Product Name' : name,
            'Description' : description,
            'Wholesale Price' : product['Wholesale Price'],
            'Packet Format' : product['Packet Format'],
            'Vat' : product['Vat'],
            'On Promo' : on_promo,
            'Promotional Price' : promo_price
        }
