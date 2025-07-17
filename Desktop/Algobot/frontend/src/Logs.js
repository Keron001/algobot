import React, { useEffect, useState } from 'react';
import { useAuth } from './App';
import {
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  Typography, CircularProgress, Snackbar, Alert, Box, Chip
} from '@mui/material';

const API = 'http://localhost:5000';

function levelColor(level) {
  switch ((level || '').toLowerCase()) {
    case 'error': return 'error';
    case 'warning': return 'warning';
    case 'info': return 'info';
    case 'debug': return 'default';
    default: return 'default';
  }
}

export default function Logs() {
  const { token } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState('');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fetchLogs = async () => {
      setLoading(true);
      setMsg('');
      try {
        const res = await fetch(`${API}/logs`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          setLogs(await res.json());
        } else {
          setMsg('Failed to fetch logs');
          setOpen(true);
        }
      } catch {
        setMsg('Network error');
        setOpen(true);
      }
      setLoading(false);
    };
    fetchLogs();
    // eslint-disable-next-line
  }, []);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Logs</Typography>
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <CircularProgress />
        </Box>
      ) : logs.length > 0 ? (
        <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                <TableCell>Level</TableCell>
                <TableCell>Message</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {logs.map((l, i) => (
                <TableRow key={i}>
                  <TableCell>{l.timestamp}</TableCell>
                  <TableCell>
                    <Chip label={l.level} color={levelColor(l.level)} size="small" />
                  </TableCell>
                  <TableCell>{l.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Typography color="text.secondary" sx={{ mt: 2 }}>No logs found.</Typography>
      )}
      <Snackbar open={open} autoHideDuration={4000} onClose={() => setOpen(false)}>
        <Alert severity="error" onClose={() => setOpen(false)}>{msg}</Alert>
      </Snackbar>
    </Box>
  );
} 