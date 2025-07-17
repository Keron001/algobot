import React, { useEffect, useState } from 'react';
import { useAuth } from './App';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Card, CardContent, Typography, CircularProgress, Snackbar, Alert, Box } from '@mui/material';

const API = 'http://localhost:5000';

export default function Chart() {
  const { token } = useAuth();
  const [equityCurve, setEquityCurve] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState('');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fetchTrades = async () => {
      setLoading(true);
      setMsg('');
      try {
        const res = await fetch(`${API}/trades`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const trades = await res.json();
          // Compute equity curve
          let equity = 0;
          const curve = trades.map(t => {
            equity += Number(t.profit) || 0;
            return { time: t.timestamp, equity: Number(equity.toFixed(2)) };
          });
          setEquityCurve(curve);
        } else {
          setMsg('Failed to fetch trades');
          setOpen(true);
        }
      } catch {
        setMsg('Network error');
        setOpen(true);
      }
      setLoading(false);
    };
    fetchTrades();
    // eslint-disable-next-line
  }, []);

  return (
    <Card sx={{ maxWidth: 800, margin: 'auto', mb: 3 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>Equity Curve</Typography>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : equityCurve.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={equityCurve} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={false} />
              <YAxis domain={['auto', 'auto']} />
              <Tooltip />
              <Line type="monotone" dataKey="equity" stroke="#007b3a" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <Typography color="text.secondary" sx={{ mt: 2 }}>No equity data found.</Typography>
        )}
        <Snackbar open={open} autoHideDuration={4000} onClose={() => setOpen(false)}>
          <Alert severity="error" onClose={() => setOpen(false)}>{msg}</Alert>
        </Snackbar>
      </CardContent>
    </Card>
  );
} 