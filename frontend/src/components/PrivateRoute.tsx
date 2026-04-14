import { Navigate } from 'react-router-dom';

export const PrivateRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
};
