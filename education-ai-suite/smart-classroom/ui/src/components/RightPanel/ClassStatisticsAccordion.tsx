import React, { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setClassStatistics } from '../../redux/slices/fetchClassStatistics';
import { getClassStatistics } from '../../services/api';
import Accordion from '../common/Accordion';

const ClassStatisticsAccordion: React.FC = () => {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const classStatistics = useAppSelector((state) => state.classStatistics.statistics);

  useEffect(() => {
    const fetchData = async () => {
      if (sessionId) {
        try {
          const data = await getClassStatistics(sessionId);
          dispatch(setClassStatistics(data));
        } catch (error) {
          console.error('Failed to fetch class statistics:', error);
        }
      }
    };

    fetchData();
  }, [sessionId, dispatch]);

  return (
    <Accordion title="Class Statistics">
      <div className="accordion-content">
        <p>
          <strong>Student Count:</strong> {classStatistics.student_count}
        </p>
        <p>
          <strong>Stand Count:</strong> {classStatistics.stand_count}
        </p>
        <p>
          <strong>Raise Up Count:</strong> {classStatistics.raise_up_count}
        </p>
        <h4>Stand Re-ID Data:</h4>
        <ul>
          {classStatistics.stand_reid.map((entry) => (
            <li key={entry.student_id}>
              Student ID: {entry.student_id}, Count: {entry.count}
            </li>
          ))}
        </ul>
      </div>
    </Accordion>
  );
};

export default ClassStatisticsAccordion;