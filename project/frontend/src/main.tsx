import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import './index.css';
import { store } from './store/store';
import Dashboard from './ui/dashboard/Dashboard';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <Dashboard />
    </Provider>
  </StrictMode>,
);
