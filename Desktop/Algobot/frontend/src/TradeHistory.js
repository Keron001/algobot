import React, { useEffect, useState } from 'react';
import { useAuth } from './App';
import {
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  Typography, CircularProgress, Snackbar, Alert, Box
} from '@mui/material';

const API = 'http://localhost:5000';

export default function TradeHistory() {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
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
          setTrades(await res.json());
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
    <Box>
      <Typography variant="h5" gutterBottom>Trade History</Typography>
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <CircularProgress />
        </Box>
      ) : trades.length > 0 ? (
        <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Volume</TableCell>
                <TableCell>Price</TableCell>
                <TableCell>Profit</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {trades.map((t, i) => (
                <TableRow key={i}>
                  <TableCell>{t.timestamp}</TableCell>
                  <TableCell>{t.symbol}</TableCell>
                  <TableCell>{t.type}</TableCell>
                  <TableCell>{t.volume}</TableCell>
                  <TableCell>{t.price}</TableCell>
                  <TableCell>{t.profit}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Typography color="text.secondary" sx={{ mt: 2 }}>No trades found.</Typography>
      )}
      <Snackbar open={open} autoHideDuration={4000} onClose={() => setOpen(false)}>
        <Alert severity="error" onClose={() => setOpen(false)}>{msg}</Alert>
      </Snackbar>
    </Box>
  );
} 