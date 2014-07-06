Create EPUB
===========

Simple ``python`` script to convert documents to **EPUB** format. To use
this tool, you have to create a **JSON** file describing the document to
create and some options how to create the final **EPUB** file.

Sample JSON file
----------------

A typical **JSON** description could look like this:

    {
        "title" : "First Awesome Book",
        "bookdir" : "/home/user/books",
        "filename" : "Awesome-Book.docx",
        "outname" : "Awesome_Book",
        "authors" : "Author Name",

        "cover" : "/home/user/pictures/cover-awsome-book.jpg",
        "comments" : "This is a totally awesome book!",
        "language" : "de",
        "outdir" : "/home/user/epubs"
    }

This will convert the file ``/home/user/books/Awsome-Book.docx`` to an
**EPUB** version ``/home/user/epubs/Awsome_Book.epub`` containing the
cover image ``/home/user/pictures/cover-awsome-book.jpg``. It will
also include the comment *This is a totally awesome book!*.

Usage
-----

Let's assume, the **JSON** file above has been saved to a file named
``awesome_book.json``. To convert the book, you simply have to issue
the following command:

    python cepub.py some_dir/awesome_book.json
