from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime
from pathlib import Path
import json
import re

app = Flask(__name__)
app.secret_key = "library-management-local-key"

DATA_FILE = Path(__file__).with_name("library_data.json")
LATE_FEE_PER_DAY = 5
LOAN_PERIOD_DAYS = 14

CATEGORIES = [
    "General", "Science", "Arts", "Science Fiction", "Fairy Tale",
    "Horror", "Mystery", "History", "Technology", "Fantasy",
    "Adventure", "Literature", "Biography"
]


class Book:
    def __init__(
        self, book_id, title, author, available=True, issued_count=0,
        issued_to="", category="General", issued_date=None
    ):
        self.book_id = str(book_id)
        self.title = title
        self.author = author
        self.available = bool(available)
        self.issued_count = int(issued_count or 0)
        self.issued_to = str(issued_to or "")
        self.category = category if category in CATEGORIES else "General"
        self.issued_date = issued_date


class Student:
    def __init__(self, student_id, name):
        self.student_id = str(student_id)
        self.name = name


class Library:
    def __init__(self):
        self.books = []
        self.students = []
        self.load_data()

    def load_data(self):
        if not DATA_FILE.exists():
            self.save_data()
            return

        try:
            with DATA_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            data = {"books": [], "students": []}

        self.books = [
            Book(
                book.get("book_id", ""),
                book.get("title", ""),
                book.get("author", ""),
                book.get("available", True),
                book.get("issued_count", 0),
                book.get("issued_to", ""),
                book.get("category", "General"),
                book.get("issued_date")
            )
            for book in data.get("books", [])
        ]
        self.students = [
            Student(student.get("student_id", ""), student.get("name", ""))
            for student in data.get("students", [])
        ]

    def save_data(self):
        data = {
            "books": [
                {
                    "book_id": book.book_id,
                    "title": book.title,
                    "author": book.author,
                    "category": book.category,
                    "available": book.available,
                    "issued_count": book.issued_count,
                    "issued_to": book.issued_to,
                    "issued_date": book.issued_date
                }
                for book in self.books
            ],
            "students": [
                {"student_id": student.student_id, "name": student.name}
                for student in self.students
            ]
        }
        with DATA_FILE.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def find_book(self, book_id):
        return next((book for book in self.books if book.book_id == str(book_id)), None)

    def find_student(self, student_id):
        return next(
            (student for student in self.students if student.student_id == str(student_id)),
            None
        )


library = Library()


@app.route("/")
def index():
    search = request.args.get("search", "").strip()
    selected_category = request.args.get("category", "All")
    selected_status = request.args.get("status", "All")

    filtered_books = library.books[:]
    if search:
        search_lower = search.lower()
        filtered_books = [
            book for book in filtered_books
            if search_lower in book.book_id.lower()
            or search_lower in book.title.lower()
            or search_lower in book.author.lower()
            or search_lower in book.category.lower()
        ]

    if selected_category != "All":
        filtered_books = [
            book for book in filtered_books if book.category == selected_category
        ]

    if selected_status == "Available":
        filtered_books = [book for book in filtered_books if book.available]
    elif selected_status == "Issued":
        filtered_books = [book for book in filtered_books if not book.available]

    stats = {
        "total_books": len(library.books),
        "available_books": sum(book.available for book in library.books),
        "issued_books": sum(not book.available for book in library.books),
        "total_students": len(library.students)
    }

    return render_template(
        "index.html",
        books=filtered_books,
        all_books=library.books,
        issued_books=[book for book in library.books if not book.available],
        students=library.students,
        categories=CATEGORIES,
        stats=stats,
        search=search,
        selected_category=selected_category,
        selected_status=selected_status,
        today=date.today().isoformat(),
        returned_details=({
            "book": request.args.get("book", ""),
            "student": request.args.get("student", ""),
            "issue_date": request.args.get("issue_date", ""),
            "return_date": request.args.get("return_date", ""),
            "days": request.args.get("days", "0"),
            "late_days": request.args.get("late_days", "0"),
            "fee": request.args.get("fee", "0")
        } if request.args.get("returned") == "1" else None)
    )


@app.route("/books/add", methods=["POST"])
def add_book():
    book_id = request.form.get("book_id", "").strip()
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    category = request.form.get("category", "General").strip()

    if not book_id:
        flash("Book ID is required.", "error")
    elif not re.fullmatch(r"[0-9]+", book_id):
        flash("Book ID must contain numbers only.", "error")
    elif not title:
        flash("Book title is required.", "error")
    elif not re.fullmatch(r"[^\W\d_]+(?:[ '-][^\W\d_]+)*", title, re.UNICODE):
        flash("Book title must contain letters only; spaces, apostrophes and hyphens are allowed.", "error")
    elif not author:
        flash("Author name is required.", "error")
    elif not re.fullmatch(r"[^\W\d_]+(?:[ '-][^\W\d_]+)*", author, re.UNICODE):
        flash("Author name must contain letters only; numbers and symbols are not allowed.", "error")
    elif library.find_book(book_id):
        flash("That book ID already exists. Please use a unique ID.", "error")
    elif category not in CATEGORIES:
        flash("Please choose a valid category.", "error")
    else:
        library.books.append(Book(book_id, title, author, category=category))
        library.save_data()
        flash(f'"{title}" was added to the library.', "success")

    return redirect(url_for("index") + "#add-book")


@app.route("/students/add", methods=["POST"])
def add_student():
    student_id = request.form.get("student_id", "").strip()
    name = request.form.get("name", "").strip()

    if not student_id:
        flash("Student ID is required.", "error")
    elif not re.fullmatch(r"[A-Za-z0-9]+", student_id):
        flash("Student ID must be alphanumeric (letters and numbers only).", "error")
    elif not name:
        flash("Student name is required.", "error")
    elif not re.fullmatch(r"[^\W\d_]+(?:[ '-][^\W\d_]+)*", name, re.UNICODE):
        flash("Student name must contain letters only (spaces, apostrophes or hyphens are allowed).", "error")
    elif library.find_student(student_id):
        flash("That student ID already exists.", "error")
    else:
        library.students.append(Student(student_id, name))
        library.save_data()
        flash(f"Student {name} was added.", "success")

    return redirect(url_for("index") + "#students")


@app.route("/students/delete/<student_id>", methods=["POST"])
def delete_student(student_id):
    student = library.find_student(student_id)
    if not student:
        flash("Student not found.", "error")
    else:
        issued = [book for book in library.books if not book.available and book.issued_to == student_id]
        if issued:
            titles = ", ".join(book.title for book in issued)
            flash(f"Cannot delete {student.name}: this student currently has an issued book ({titles}). Return the book first.", "error")
        else:
            library.students.remove(student)
            library.save_data()
            flash(f"Student {student.name} was removed.", "success")
    return redirect(url_for("index") + "#students")


@app.route("/books/delete/<book_id>", methods=["POST"])
def delete_book(book_id):
    book = library.find_book(book_id)
    if not book:
        flash("Book not found.", "error")
    elif not book.available:
        student = library.find_student(book.issued_to)
        borrower = student.name if student else book.issued_to or "an unknown student"
        flash(f'Cannot delete "{book.title}": it is currently issued to {borrower}. Return the book first.', "error")
    else:
        library.books.remove(book)
        library.save_data()
        flash(f'Book "{book.title}" was deleted.', "success")
    return redirect(url_for("index") + "#books")


@app.route("/books/issue", methods=["POST"])
def issue_book():
    book_id = request.form.get("book_id", "").strip()
    student_id = request.form.get("student_id", "").strip()
    book = library.find_book(book_id)
    student = library.find_student(student_id)

    if not book:
        flash("Book ID not found.", "error")
    elif not student:
        flash("Student ID not found.", "error")
    elif not book.available:
        flash("This book is already issued.", "error")
    else:
        book.available = False
        book.issued_to = student.student_id
        book.issued_date = date.today().isoformat()
        book.issued_count += 1
        library.save_data()
        flash(f'"{book.title}" issued to {student.name}.', "success")

    return redirect(url_for("index") + "#issue-return")


@app.route("/books/return", methods=["POST"])
def return_book():
    book_id = request.form.get("book_id", "").strip()
    book = library.find_book(book_id)

    if not book:
        flash("Book ID not found. Please select an issued book.", "error")
        return redirect(url_for("index") + "#issue-return")
    if book.available:
        flash("This book is not currently issued.", "error")
        return redirect(url_for("index") + "#issue-return")

    return_date_text = request.form.get("return_date", date.today().isoformat()).strip()
    # Older records may not contain an issue date. In that case, ask the librarian
    # to provide it instead of silently calculating a zero-day loan.
    issued_date_text = book.issued_date or request.form.get("issued_date_override", "").strip()
    try:
        return_on = datetime.strptime(return_date_text, "%Y-%m-%d").date()
        if not issued_date_text:
            flash("This issued book has no saved issue date. Enter its issue date to calculate the loan duration and fine.", "error")
            return redirect(url_for("index") + "#issue-return")
        issued_on = datetime.strptime(issued_date_text, "%Y-%m-%d").date()
        if issued_on > date.today():
            flash("Issue date cannot be in the future.", "error")
            return redirect(url_for("index") + "#issue-return")
        if return_on < issued_on:
            flash("Return date cannot be earlier than the issue date.", "error")
            return redirect(url_for("index") + "#issue-return")
    except (ValueError, TypeError):
        flash("Please choose valid issue and return dates.", "error")
        return redirect(url_for("index") + "#issue-return")

    days_kept = (return_on - issued_on).days
    late_days = max(0, days_kept - LOAN_PERIOD_DAYS)
    fee = late_days * LATE_FEE_PER_DAY
    title = book.title
    student_id = book.issued_to
    student = library.find_student(student_id)
    student_name = student.name if student else student_id or "Unknown student"
    issue_iso = issued_on.isoformat()
    return_iso = return_on.isoformat()

    book.available = True
    book.issued_to = ""
    book.issued_date = None
    library.save_data()

    return redirect(url_for(
        "index",
        returned="1",
        book=title,
        student=student_name,
        issue_date=issue_iso,
        return_date=return_iso,
        days=days_kept,
        late_days=late_days,
        fee=fee
    ) + "#issue-return")


if __name__ == "__main__":
    app.run(debug=True)
