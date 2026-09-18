# Friend on Campus (FoC) - Frontend Application

A simple, lightweight **React + Vite** frontend prototype for **Friend on Campus (FoC)**.

## How to Run

1. Open your terminal and navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the local development server:
   ```bash
   npm run dev
   ```

4. Open the displayed URL (usually `http://localhost:5173`) in your browser.

---

## App Features & Sections

- **Role Mode Toggle**: Switch between **Requester** and **Courier** mode from the top navigation bar.
- **Campus Stores & Suppliers**: Browse campus food courts, cafes, and facility stations (e.g. *CoffeeBean @ COM3*, *Printers @ PC Commons*, *The Terrace @ COM3*). Filter by category or search by location.
- **Requester Errand Creation**:
  - Click *"Request Errand Here"* on any supplier to open the order modal.
  - Enter pickup details, destination, and instructions.
  - Automatically holds **1 Credit** in escrow.
  - View order status transitions (*OPEN* $\rightarrow$ *ACCEPTED* $\rightarrow$ *PICKED UP* $\rightarrow$ *DELIVERED* $\rightarrow$ *COMPLETED*).
  - Cancel open orders or confirm delivery to release the reward.
- **Courier Flow**:
  - View open requests across campus.
  - Built-in prevention against accepting your own requests.
  - Accept an open errand to start the active delivery flow.
  - Update fulfillment milestones (*Mark Items as Picked Up* $\rightarrow$ *Mark Errand as Delivered*).
- **Closed Credit Economy Ledger**:
  - Real-time balance badge in the header.
  - Dedicated ledger tab tracking initial allocations, escrow holds, releases, and completed transfers.
- **Student Profile**: View account status, email, and update profile info.
