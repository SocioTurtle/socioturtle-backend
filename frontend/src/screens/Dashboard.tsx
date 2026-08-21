import { Button, Card } from "../components/ui";
import { useAuth } from "../core/hooks/useAuth";

/**
 * Every SocioTurtle account gets both experiences — there's no separate
 * student-only or mentor-only account, so this is one screen with two
 * sections rather than role-based routing.
 */
export function Dashboard({ onGoToResources }: { onGoToResources: () => void }) {
  const { user } = useAuth();

  return (
    <div className="dashboard">
      <h1>Welcome, {user?.username}</h1>
      <p className="muted">You have both the student and mentor experience on this account.</p>

      <Card className="dashboard-section">
        <h2>As a student</h2>
        <p className="muted">Find and save learning resources shared by mentors.</p>
        <Button variant="ghost" onClick={onGoToResources}>
          Browse resources
        </Button>
      </Card>

      <Card className="dashboard-section">
        <h2>As a mentor</h2>
        <p className="muted">
          Browse what's been shared, or point students toward resources worth exploring.
        </p>
        <Button variant="ghost" onClick={onGoToResources}>
          Browse resources
        </Button>
      </Card>
    </div>
  );
}
