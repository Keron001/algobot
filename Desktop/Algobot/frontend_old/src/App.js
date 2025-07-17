import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const API = 'http://localhost:5000';

function ChartPage({ trades }) {
  // Calculate cumulative P&L
  let data = [];
  let cumProfit = 0;
  trades.slice().reverse().forEach(t => {
    cumProfit += t.profit;
    data.push({
      time: t.timestamp.slice(0, 19).replace('T', ' '),
      equity: cumProfit
    });
  });
  data = data.reverse();
  return (
    <div>
      <h2>Equity Curve</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" minTickGap={40} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="equity" stroke="#8884d8" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function App() {
  const [page, setPage] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState('');
  const [status, setStatus] = useState('');
  const [mt5, setMt5] = useState({ login: '', password: '', server: '' });
  const [msg, setMsg] = useState('');
  const [trades, setTrades] = useState([]);
  const [logs, setLogs] = useState([]);

  const handleAuth = async (route) => {
    setMsg('');
    const res = await fetch(`${API}/${route}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (res.ok && data.access_token) {
      setToken(data.access_token);
      setPage('dashboard');
    } else if (res.ok) {
      setMsg(data.msg);
      if (route === 'register') setPage('login');
    } else {
      setMsg(data.msg || 'Error');
    }
  };

  const fetchStatus = async () => {
    const res = await fetch(`${API}/bot/status`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setStatus(data.status);
  };

  const startBot = async () => {
    await fetch(`${API}/bot/start`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    });
    fetchStatus();
  };

  const stopBot = async () => {
    await fetch(`${API}/bot/stop`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    });
    fetchStatus();
  };

  const updateMt5 = async () => {
    await fetch(`${API}/mt5`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(mt5)
    });
    setMsg('MT5 credentials updated');
  };

  // Fetch trades
  const fetchTrades = async () => {
    const res = await fetch(`${API}/trades`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) setTrades(await res.json());
  };

  // Fetch logs
  const fetchLogs = async () => {
    const res = await fetch(`${API}/logs`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) setLogs(await res.json());
  };

  const handleLogout = () => {
    setToken('');
    setPage('login');
  };

  if (page === 'login') {
    return (
      <div style={{ maxWidth: 400, margin: 'auto', padding: 20 }}>
        <h2>Login</h2>
        <input placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} /><br />
        <input placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} /><br />
        <button onClick={() => handleAuth('login')}>Login</button>
        <button onClick={() => setPage('register')}>Register</button>
        <div style={{ color: 'red' }}>{msg}</div>
      </div>
    );
  }
  if (page === 'register') {
    return (
      <div style={{ maxWidth: 400, margin: 'auto', padding: 20 }}>
        <h2>Register</h2>
        <input placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} /><br />
        <input placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} /><br />
        <button onClick={() => handleAuth('register')}>Register</button>
        <button onClick={() => setPage('login')}>Back to Login</button>
        <div style={{ color: 'red' }}>{msg}</div>
      </div>
    );
  }
  // Dashboard
  return (
    <div style={{ maxWidth: 600, margin: 'auto', padding: 20 }}>
      <h1>AlgoBot Dashboard</h1>
      {token && (
        <nav>
          <button onClick={() => setPage('dashboard')}>Dashboard</button>
          <button onClick={() => { fetchTrades(); setPage('trades'); }}>Trades</button>
          <button onClick={() => { fetchLogs(); setPage('logs'); }}>Logs</button>
          <button onClick={() => setPage('chart')}>Chart</button>
          <button onClick={handleLogout}>Logout</button>
        </nav>
      )}
      <h2>AlgoBot Dashboard</h2>
      <button onClick={fetchStatus}>Refresh Status</button>
      <button onClick={startBot}>Start Bot</button>
      <button onClick={stopBot}>Stop Bot</button>
      <div>Status: <b>{status}</b></div>
      <h3>MT5 Credentials</h3>
      <input placeholder="Login" value={mt5.login} onChange={e => setMt5({ ...mt5, login: e.target.value })} /><br />
      <input placeholder="Password" type="password" value={mt5.password} onChange={e => setMt5({ ...mt5, password: e.target.value })} /><br />
      <input placeholder="Server" value={mt5.server} onChange={e => setMt5({ ...mt5, server: e.target.value })} /><br />
      <button onClick={updateMt5}>Update MT5 Credentials</button>
      <div style={{ color: 'green' }}>{msg}</div>
      {page === 'trades' && (
        <div>
          <h2>Trade History</h2>
          <table border="1" cellPadding="5">
            <thead>
              <tr>
                <th>Time</th><th>Symbol</th><th>Type</th><th>Volume</th><th>Price</th><th>Profit</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={i}>
                  <td>{t.timestamp}</td>
                  <td>{t.symbol}</td>
                  <td>{t.type}</td>
                  <td>{t.volume}</td>
                  <td>{t.price}</td>
                  <td>{t.profit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {page === 'logs' && (
        <div>
          <h2>Logs</h2>
          <ul>
            {logs.map((l, i) => (
              <li key={i}><b>{l.timestamp}</b> [{l.level}] {l.message}</li>
            ))}
          </ul>
        </div>
      )}
      {page === 'chart' && <ChartPage trades={trades} />}
      {/* ... add chart here in future ... */}
    </div>
  );
}

export default App; 