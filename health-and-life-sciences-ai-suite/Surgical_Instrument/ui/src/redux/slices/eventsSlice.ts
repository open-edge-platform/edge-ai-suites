// src/redux/slices/eventsSlice.ts
import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface Event {
  id: string;
  workload: string;
  timestamp: number;
  data: any;
}

interface EventsState {
  all: Event[];
  byWorkload: Record<string, Event[]>;
}

const initialState: EventsState = {
  all: [],
  byWorkload: {
    rppg: [],
    'ai-ecg': [],
    mdpnp: [],
    '3d-pose': [],
  },
};

const eventsSlice = createSlice({
  name: 'events',
  initialState,
  reducers: {
    addEvent: (state, action: PayloadAction<Event>) => {
      const event = action.payload;
      state.all.push(event);
      
      if (state.byWorkload[event.workload]) {
        state.byWorkload[event.workload].push(event);
        if (state.byWorkload[event.workload].length > 100) {
          state.byWorkload[event.workload].shift();
        }
      }
      
      if (state.all.length > 500) {
        state.all.shift();
      }
    },
    clearEvents: (state) => {
      state.all = [];
      Object.keys(state.byWorkload).forEach((key) => {
        state.byWorkload[key] = [];
      });
    },
  },
});

export const { addEvent, clearEvents } = eventsSlice.actions;
export default eventsSlice.reducer;