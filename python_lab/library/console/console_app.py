from .console_state import ConsoleState
from .common_actions import CommonActions
from application_core.interfaces.ipatron_repository import IPatronRepository
from application_core.interfaces.iloan_repository import ILoanRepository
from application_core.interfaces.iloan_service import ILoanService
from application_core.interfaces.ipatron_service import IPatronService
from infrastructure.json_data import JsonData  # added import

class ConsoleApp:
    def __init__(
        self,
        loan_service: ILoanService,
        patron_service: IPatronService,
        patron_repository: IPatronRepository,
        loan_repository: ILoanRepository,
        json_data: JsonData = None  # added parameter
    ):
        self._current_state: ConsoleState = ConsoleState.PATRON_SEARCH
        self.matching_patrons = []
        self.selected_patron_details = None
        self.selected_loan_details = None
        self._patron_repository = patron_repository
        self._loan_repository = loan_repository
        self._loan_service = loan_service
        self._patron_service = patron_service
        self._json_data = json_data  # store JsonData for direct access to Books/BookItems/Loans

    def write_input_options(self, options):
        print("Input Options:")
        if options & CommonActions.RETURN_LOANED_BOOK:
            print(' - "r" to mark as returned')
        if options & CommonActions.EXTEND_LOANED_BOOK:
            print(' - "e" to extend the book loan')
        if options & CommonActions.RENEW_PATRON_MEMBERSHIP:
            print(' - "m" to extend patron\'s membership')
        if options & CommonActions.SEARCH_PATRONS:
            print(' - "s" for new search')
        if options & CommonActions.SEARCH_BOOKS:
            print(' - "b" to check for book availability')
        if options & CommonActions.QUIT:
            print(' - "q" to quit')
        if options & CommonActions.SELECT:
            print(' - type a number to select a list item.')

    def run(self) -> None:
        while True:
            if self._current_state == ConsoleState.PATRON_SEARCH:
                self._current_state = self.patron_search()
            elif self._current_state == ConsoleState.PATRON_SEARCH_RESULTS:
                self._current_state = self.patron_search_results()
            elif self._current_state == ConsoleState.PATRON_DETAILS:
                self._current_state = self.patron_details()
            elif self._current_state == ConsoleState.LOAN_DETAILS:
                self._current_state = self.loan_details()
            elif self._current_state == ConsoleState.QUIT:
                break

    def patron_search(self) -> ConsoleState:
        search_input = input("Enter a string to search for patrons by name: ").strip()
        if not search_input:
            print("No input provided. Please try again.")
            return ConsoleState.PATRON_SEARCH
        self.matching_patrons = self._patron_repository.search_patrons(search_input)
        if not self.matching_patrons:
            print("No matching patrons found.")
            return ConsoleState.PATRON_SEARCH
        return ConsoleState.PATRON_SEARCH_RESULTS

    def patron_search_results(self) -> ConsoleState:
        print("\nMatching Patrons:")
        idx = 1
        for patron in self.matching_patrons:
            print(f"{idx}) {patron.name}")
            idx += 1
        if self.matching_patrons:
            self.write_input_options(
                CommonActions.SELECT | CommonActions.SEARCH_PATRONS | CommonActions.QUIT
            )
        else:
            self.write_input_options(
                CommonActions.SEARCH_PATRONS | CommonActions.QUIT
            )
        selection = input("Enter your choice: ").strip().lower()
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        elif selection.isdigit():
            idx = int(selection)
            if 1 <= idx <= len(self.matching_patrons):
                self.selected_patron_details = self.matching_patrons[idx - 1]
                return ConsoleState.PATRON_DETAILS
            else:
                print("Invalid selection. Please enter a valid number.")
                return ConsoleState.PATRON_SEARCH_RESULTS
        else:
            print("Invalid input. Please enter a number, 's', or 'q'.")
            return ConsoleState.PATRON_SEARCH_RESULTS

    def patron_details(self) -> ConsoleState:
        patron = self.selected_patron_details
        print(f"\nName: {patron.name}")
        print(f"Membership Expiration: {patron.membership_end}")
        loans = self._loan_repository.get_loans_by_patron_id(patron.id)
        print("\nBook Loans History:")

        valid_loans = self._print_loans(loans)

        if valid_loans:
            options = (
                CommonActions.RENEW_PATRON_MEMBERSHIP
                | CommonActions.SEARCH_PATRONS
                | CommonActions.QUIT
                | CommonActions.SELECT
                | CommonActions.SEARCH_BOOKS  # added SEARCH_BOOKS
            )
            selection = self._get_patron_details_input(options)
            # If the user selected the search-books action, prompt for a title now
            if selection == 'b':
                book_title = input("Enter a book title to search for: ").strip()
                if not book_title:
                    print("No input provided. Returning to patron details.")
                    return ConsoleState.PATRON_DETAILS
                return self.search_books(book_title)
            return self._handle_patron_details_selection(selection, patron, valid_loans)
        else:
            print("No valid loans for this patron.")
            options = (
                CommonActions.SEARCH_PATRONS
                | CommonActions.QUIT
            )
            selection = self._get_patron_details_input(options)
            return self._handle_no_loans_selection(selection)

    def _print_loans(self, loans):
        valid_loans = []
        idx = 1
        for loan in loans:
            if not getattr(loan, 'book_item', None) or not getattr(loan.book_item, 'book', None):
                print(f"{idx}) [Invalid loan data: missing book information]")
            else:
                returned = "True" if getattr(loan, 'return_date', None) else "False"
                print(f"{idx}) {loan.book_item.book.title} - Due: {loan.due_date} - Returned: {returned}")
                valid_loans.append((idx, loan))
            idx += 1
        return valid_loans

    def _get_patron_details_input(self, options):
        self.write_input_options(options)
        return input("Enter your choice: ").strip().lower()

    def _handle_patron_details_selection(self, selection, patron, valid_loans):
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        elif selection == 'm':
            status = self._patron_service.renew_membership(patron.id)
            print(status)
            self.selected_patron_details = self._patron_repository.get_patron(patron.id)
            return ConsoleState.PATRON_DETAILS
        elif selection == 'b':
            # call the new search_books method for SEARCH_BOOKS action
            return self.search_books()
        elif selection.isdigit():
            idx = int(selection)
            if 1 <= idx <= len(valid_loans):
                self.selected_loan_details = valid_loans[idx - 1][1]
                return ConsoleState.LOAN_DETAILS
            print("Invalid selection. Please enter a number shown in the list above.")
            return ConsoleState.PATRON_DETAILS
        else:
            print("Invalid input. Please enter a number, 'm', 'b', 's', or 'q'.")
            return ConsoleState.PATRON_DETAILS

    def _handle_no_loans_selection(self, selection):
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        else:
            print("Invalid input.")
            return ConsoleState.PATRON_DETAILS

    def loan_details(self) -> ConsoleState:
        loan = self.selected_loan_details
        print(f"\nBook title: {loan.book_item.book.title}")
        print(f"Book Author: {loan.book_item.book.author.name}")
        print(f"Due date: {loan.due_date}")
        returned = "True" if getattr(loan, 'return_date', None) else "False"
        print(f"Returned: {returned}\n")
        options = CommonActions.SEARCH_PATRONS | CommonActions.QUIT
        if not getattr(loan, 'return_date', None):
            options |= CommonActions.RETURN_LOANED_BOOK | CommonActions.EXTEND_LOANED_BOOK
        self.write_input_options(options)
        selection = input("Enter your choice: ").strip().lower()
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        elif selection == 'r' and not getattr(loan, 'return_date', None):
            status = self._loan_service.return_loan(loan.id)
            print("Book was successfully returned.")
            print(status)
            self.selected_loan_details = self._loan_repository.get_loan(loan.id)
            return ConsoleState.LOAN_DETAILS
        elif selection == 'e' and not getattr(loan, 'return_date', None):
            status = self._loan_service.extend_loan(loan.id)
            print(status)
            self.selected_loan_details = self._loan_repository.get_loan(loan.id)
            return ConsoleState.LOAN_DETAILS
        else:
            print("Invalid input.")
            return ConsoleState.LOAN_DETAILS

    def search_books(self, book_title=None) -> ConsoleState:
        # Allow repeated searches; return to patron details when user chooses to go back.
        while True:
            if book_title is None:
                book_title = input("Enter a book title to search for (partial or full): ").strip()
                if not book_title:
                    print("No input provided. Returning to patron details.")
                    return ConsoleState.PATRON_DETAILS

            # Load books from JsonData if available, else try repository
            books = []
            if self._json_data and getattr(self._json_data, "books", None) is not None:
                books = self._json_data.books
            elif hasattr(self._patron_repository, "get_all_books"):
                try:
                    books = self._patron_repository.get_all_books()
                except Exception:
                    books = []

            # Case-insensitive partial match
            matches = [b for b in books if book_title.lower() in getattr(b, "title", "").lower()]

            if not matches:
                print(f"No book found with title matching: {book_title}")
            elif len(matches) > 1:
                print("Multiple books match:")
                for idx, b in enumerate(matches, start=1):
                    print(f"{idx}) {getattr(b, 'title', 'Unknown')}")
                sel = input("Enter number to select a book, 'r' to refine search, or 'b' to go back: ").strip().lower()
                if sel == "b":
                    return ConsoleState.PATRON_DETAILS
                if sel == "r":
                    book_title = None
                    continue
                if sel.isdigit() and 1 <= int(sel) <= len(matches):
                    selected = matches[int(sel) - 1]
                else:
                    print("Invalid selection.")
                    book_title = None
                    continue
            else:
                selected = matches[0]

            # Find all book items (physical copies) for the selected book
            items = []
            if self._json_data and getattr(self._json_data, "book_items", None) is not None:
                items = [bi for bi in self._json_data.book_items if getattr(bi, "book_id", None) == getattr(selected, "id", None)]
            elif hasattr(self._patron_repository, "get_all_book_items"):
                try:
                    items_all = self._patron_repository.get_all_book_items()
                    items = [bi for bi in items_all if getattr(bi, "book_id", None) == getattr(selected, "id", None)]
                except Exception:
                    items = []

            if not items:
                print(f"No physical copy found for '{getattr(selected, 'title', 'Unknown')}'.")
            else:
                # Load loans and determine if copies are on loan (ReturnDate is null)
                loans = []
                if self._json_data and getattr(self._json_data, "loans", None) is not None:
                    loans = self._json_data.loans
                elif hasattr(self._loan_repository, "get_all_loans"):
                    try:
                        loans = self._loan_repository.get_all_loans()
                    except Exception:
                        loans = []

                # For each copy, check for an active loan (return_date is None)
                active_loans = []
                for bi in items:
                    for l in loans:
                        if getattr(l, "book_item_id", None) == getattr(bi, "id", None) and getattr(l, "return_date", None) is None:
                            active_loans.append(l)
                            break

                if len(active_loans) < len(items):
                    print(f"'{getattr(selected, 'title', 'Unknown')}' is available for loan.")
                    # Offer checkout if a patron is selected
                    if getattr(self, 'selected_patron_details', None):
                        patron = self.selected_patron_details
                        confirm = input(f"Would you like to check out '{getattr(selected, 'title', 'Unknown')}' for {patron.name}? (y/n): ").strip().lower()
                        if confirm == 'y':
                            # choose first available copy (book item not in active loans)
                            active_item_ids = {getattr(l, 'book_item_id', None) for l in active_loans}
                            available_item = None
                            for bi in items:
                                if getattr(bi, 'id', None) not in active_item_ids:
                                    available_item = bi
                                    break
                            if available_item is None:
                                print("No available copy found at checkout time.")
                            else:
                                try:
                                    new_loan = self._loan_service.checkout_book(patron, available_item)
                                    print(f"Checked out '{getattr(selected, 'title', 'Unknown')}' to {patron.name}. Due date: {new_loan.due_date}")
                                    # refresh patron details from repository if available
                                    try:
                                        if getattr(self._patron_repository, 'get_patron', None):
                                            self.selected_patron_details = self._patron_repository.get_patron(patron.id)
                                    except Exception:
                                        pass
                                except Exception as e:
                                    print(f"Error during checkout: {e}")
                    else:
                        print("Select a patron first to perform checkout.")
                else:
                    # All copies are on loan; show earliest due date among active loans
                    try:
                        earliest = min(active_loans, key=lambda x: x.due_date)
                        print(f"'{getattr(selected, 'title', 'Unknown')}' is on loan to another patron. The earliest return due date is {earliest.due_date}.")
                    except Exception:
                        print(f"All copies of '{getattr(selected, 'title', 'Unknown')}' are currently on loan.")

            # Allow user to search again or go back
            choice = input("Press 's' to search again or 'b' to go back: ").strip().lower()
            if choice == "s":
                book_title = None
                continue
            return ConsoleState.PATRON_DETAILS

from application_core.services.loan_service import LoanService
from application_core.services.patron_service import PatronService
from infrastructure.json_data import JsonData
from infrastructure.json_loan_repository import JsonLoanRepository
from infrastructure.json_patron_repository import JsonPatronRepository
from console.console_app import ConsoleApp

def main():
    json_data = JsonData()
    patron_repo = JsonPatronRepository(json_data)
    loan_repo = JsonLoanRepository(json_data)
    loan_service = LoanService(loan_repo)
    patron_service = PatronService(patron_repo)

    app = ConsoleApp(
        loan_service=loan_service,
        patron_service=patron_service,
        patron_repository=patron_repo,
        loan_repository=loan_repo,
        json_data=json_data
    )
    app.run()
