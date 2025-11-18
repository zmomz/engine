import React from 'react';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div>
      <header>Header Content</header>
      <nav>Sidebar Content</nav>
      <main>{children}</main>
    </div>
  );
};

export default MainLayout;
