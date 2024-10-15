class BookwalkerBook:
    def __init__(
        self,
        title,
        original_title,
        volume_number,
        part,
        date,
        is_released,
        price,
        url,
        thumbnail,
        book_type,
        description,
        preview_image_url,
    ):
        self.title = title
        self.original_title = original_title
        self.volume_number = volume_number
        self.part = part
        self.date = date
        self.is_released = is_released
        self.price = price
        self.url = url
        self.thumbnail = thumbnail
        self.book_type = book_type
        self.description = description
        self.preview_image_url = preview_image_url

    def __str__(self):
        return f"BookwalkerBook(title={self.title}, original_title={self.original_title}, volume_number={self.volume_number}, part={self.part}, date={self.date}, is_released={self.is_released}, price={self.price}, url={self.url}, thumbnail={self.thumbnail}, book_type={self.book_type}, description={self.description}, preview_image_url={self.preview_image_url})"

    def __repr__(self):
        return str(self)


class BookwalkerSeries:
    def __init__(self, title, books, book_count, book_type):
        self.title = title
        self.books = books
        self.book_count = book_count
        self.book_type = book_type

    def __str__(self):
        return f"BookwalkerSeries(title={self.title}, books={self.books}, book_count={self.book_count}, book_type={self.book_type})"

    def __repr__(self):
        return str(self)
