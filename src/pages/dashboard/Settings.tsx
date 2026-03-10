import { useAuth } from "@/contexts/AuthContext";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function SettingsPage() {
  const { profile, user } = useAuth();
  const [fullName, setFullName] = useState(profile?.full_name ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    const { error } = await supabase.from("profiles").update({ full_name: fullName }).eq("auth_user_id", user.id);
    setSaving(false);
    if (error) toast.error(error.message);
    else toast.success("Profile updated");
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Account Settings</h1>
        <p className="mt-1 text-muted-foreground">Manage your profile and preferences.</p>
      </div>
      <div className="max-w-md space-y-4 rounded-xl border p-6">
        <div className="space-y-2">
          <Label>Email</Label>
          <Input value={profile?.email ?? ""} disabled />
        </div>
        <div className="space-y-2">
          <Label>Full Name</Label>
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <Button onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save Changes"}</Button>
      </div>
    </div>
  );
}
