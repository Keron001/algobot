import React, { useEffect, useState } from 'react';
import { useAuth } from './App';
import {
  Card, CardContent, Typography, Button, TextField, Box, CircularProgress, Snackbar, Alert, Stack
} from '@mui/material';

const API = 'http://localhost:5000';

export default function BotControl() {
  const { token } = useAuth();
  const [status, setStatus] = useState('');
  const [msg, setMsg] = useState('');
  const [mt5, setMt5] = useState({ login: '', password: '', server: '' });
  const [mt5Msg, setMt5Msg] = useState('');
  const [loading, setLoading] = useState(false);
  const [mt5Loading, setMt5Loading] = useState(false);
  const [snackOpen, setSnackOpen] = useState(false);
  const [snackMsg, setSnackMsg] = useState('');
  const [snackSeverity, setSnackSeverity] = useState('success');

  // Fetch bot status
  const fetchStatus = async () => {
    setLoading(true);
    setMsg('');
    try {
      const res = await fetch(`${API}/bot/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setStatus(data.status === 'stopped' ? 'Stopped' : 'Running');
    } catch {
      setStatus('Unknown');
    }
    setLoading(false);
  };

  // Fetch MT5 credentials
  const fetchMt5 = async () => {
    setMt5Loading(true);
    setMt5Msg('');
    try {
      const res = await fetch(`${API}/mt5`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMt5({
          login: data.login || '',
          password: data.password || '',
          server: data.server || ''
        });
      }
    } catch {}
    setMt5Loading(false);
  };

  useEffect(() => {
    fetchStatus();
    fetchMt5();
    // eslint-disable-next-line
  }, []);

  // Start bot
  const startBot = async () => {
    setLoading(true);
    setMsg('');
    const res = await fetch(`${API}/start_bot`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setMsg(data.msg || '');
    setSnackMsg(data.msg || '');
    setSnackSeverity(res.ok ? 'success' : 'error');
    setSnackOpen(true);
    fetchStatus();
    setLoading(false);
  };

  // Stop bot
  const stopBot = async () => {
    setLoading(true);
    setMsg('');
    const res = await fetch(`${API}/stop_bot`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setMsg(data.msg || '');
    setSnackMsg(data.msg || '');
    setSnackSeverity(res.ok ? 'success' : 'error');
    setSnackOpen(true);
    fetchStatus();
    setLoading(false);
  };

  // Update MT5 credentials
  const updateMt5 = async (e) => {
    e.preventDefault();
    setMt5Loading(true);
    setMt5Msg('');
    const res = await fetch(`${API}/mt5`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(mt5)
    });
    const data = await res.json();
    setMt5Msg(data.msg || 'Updated');
    setSnackMsg(data.msg || 'Updated');
    setSnackSeverity(res.ok ? 'success' : 'error');
    setSnackOpen(true);
    setMt5Loading(false);
  };

  return (
    <Card sx={{ maxWidth: 600, margin: 'auto', mb: 3 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>Bot Control</Typography>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <Typography variant="body1"><b>Status:</b> {loading ? <CircularProgress size={18} /> : status}</Typography>
          <Button variant="contained" color="success" onClick={startBot} disabled={status === 'Running' || loading}>Start Bot</Button>
          <Button variant="contained" color="error" onClick={stopBot} disabled={status !== 'Running' || loading}>Stop Bot</Button>
        </Stack>
        <Box component="form" onSubmit={updateMt5} sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 400 }}>
          <Typography variant="subtitle1">MT5 Credentials</Typography>
          <TextField
            label="Login"
            value={mt5.login}
            onChange={e => setMt5({ ...mt5, login: e.target.value })}
            size="small"
            required
          />
          <TextField
            label="Password"
            type="password"
            value={mt5.password}
            onChange={e => setMt5({ ...mt5, password: e.target.value })}
            size="small"
            required
          />
          <TextField
            label="Server"
            value={mt5.server}
            onChange={e => setMt5({ ...mt5, server: e.target.value })}
            size="small"
            required
          />
          <Button type="submit" variant="outlined" disabled={mt5Loading}>{mt5Loading ? <CircularProgress size={18} /> : 'Update'}</Button>
          {mt5Msg && <Alert severity="info">{mt5Msg}</Alert>}
        </Box>
        <Snackbar open={snackOpen} autoHideDuration={4000} onClose={() => setSnackOpen(false)}>
          <Alert severity={snackSeverity} onClose={() => setSnackOpen(false)}>{snackMsg}</Alert>
        </Snackbar>
      </CardContent>
    </Card>
  );
} 