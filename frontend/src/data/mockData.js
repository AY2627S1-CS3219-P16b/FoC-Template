export const initialSuppliers = [
  {
    id: "sup-1",
    name: "Supplier 1",
    category: "F&B",
    location: "Location 1",
    operatingHours: "08:00 - 19:00",
    description: "Description 1",
    pickupNotes: "Pickup note 1",
    tags: ["Category A"]
  },
  {
    id: "sup-2",
    name: "Supplier 2",
    category: "Facilities",
    location: "Location 2",
    operatingHours: "08:00 - 22:00",
    description: "Description 2",
    pickupNotes: "Pickup note 2",
    tags: ["Category B"]
  },
  {
    id: "sup-3",
    name: "Supplier 3",
    category: "Retail",
    location: "Location 3",
    operatingHours: "09:00 - 21:00",
    description: "Description 3",
    pickupNotes: "Pickup note 3",
    tags: ["Category C"]
  },
  {
    id: "sup-4",
    name: "Supplier 4",
    category: "F&B",
    location: "Location 4",
    operatingHours: "10:00 - 20:00",
    description: "Description 4",
    pickupNotes: "Pickup note 4",
    tags: ["Category A"]
  }
];

export const initialOrders = [
  {
    id: "REQ-101",
    supplierId: "sup-1",
    supplierName: "Supplier 1",
    pickupLocation: "Location 1",
    items: "Item description 1",
    deliveryLocation: "Delivery location 1",
    instructions: "Delivery instructions 1",
    requesterName: "User 1 (You)",
    requesterId: "usr-1",
    courierName: null,
    courierId: null,
    status: "OPEN",
    creditsReward: 1,
    createdAt: "10m ago",
    deadline: "Within 1 hour"
  },
  {
    id: "REQ-102",
    supplierId: "sup-2",
    supplierName: "Supplier 2",
    pickupLocation: "Location 2",
    items: "Item description 2",
    deliveryLocation: "Delivery location 2",
    instructions: "Delivery instructions 2",
    requesterName: "User 2",
    requesterId: "usr-2",
    courierName: null,
    courierId: null,
    status: "OPEN",
    creditsReward: 1,
    createdAt: "20m ago",
    deadline: "Within 2 hours"
  }
];

export const initialTransactions = [
  {
    id: "TX-1",
    time: "2026-09-07 14:00",
    type: "CREDIT_RESERVED",
    title: "Credit Reserved",
    orderRef: "REQ-101",
    amount: -1,
    status: "HELD"
  },
  {
    id: "TX-2",
    time: "2026-09-06 10:00",
    type: "INITIAL_ALLOCATION",
    title: "Initial Allocation",
    orderRef: "SYSTEM",
    amount: 20,
    status: "COMPLETED"
  }
];
