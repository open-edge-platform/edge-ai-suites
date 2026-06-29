import { useEffect } from 'react';
import { useAppDispatch } from './store';
import { openEventStream } from './services/eventStream';
import { api } from './services/api';
import { setStatus } from './store/slices/statusSlice';
import Header from './components/Header';
import TopPanel from './components/TopPanel';
import VideoPanel from './components/VideoPanel';
import RightPanel from './components/RightPanel';
import LeftPanel from './components/LeftPanel';
import Footer from './components/Footer';
import './App.css';

export default function App() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    const handle = openEventStream(dispatch);

    // Seed initial status; SSE will keep it fresh from here.
    api.status()
      .then((s) => dispatch(setStatus(s)))
      .catch(() => { /* SSE will fill it in shortly */ });

    return () => handle.close();
  }, [dispatch]);

  return (
    <div className="app">
      <Header />
      <TopPanel />
      <main className="app-main">
        <LeftPanel />
        <VideoPanel />
        <RightPanel />
      </main>
      <Footer />
    </div>
  );
}
