import React from 'react';

export default function CreditsSection({
  availableCredits,
  reservedCredits,
  transactions
}) {
  return (
    <section>
      <div className="section-header">
        <h2>Credit Ledger</h2>
      </div>

      <div className="stats-grid">
        <div className="stat-box">
          <div className="stat-label">Available Credits</div>
          <div className="stat-number">{availableCredits}</div>
        </div>

        <div className="stat-box">
          <div className="stat-label">Reserved Credits</div>
          <div className="stat-number">{reservedCredits}</div>
        </div>

        <div className="stat-box">
          <div className="stat-label">Total Transactions</div>
          <div className="stat-number">{transactions.length}</div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ fontSize: '14px', marginBottom: '10px' }}>Recent Transactions</h3>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Order Ref</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx) => (
                <tr key={tx.id}>
                  <td>{tx.time}</td>
                  <td>{tx.title}</td>
                  <td>{tx.orderRef}</td>
                  <td>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</td>
                  <td><span className="badge">{tx.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
