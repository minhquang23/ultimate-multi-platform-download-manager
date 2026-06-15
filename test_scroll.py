import customtkinter as ctk

app = ctk.CTk()
frame = ctk.CTkScrollableFrame(app)
frame.pack()

lbl1 = ctk.CTkLabel(frame, text="Label 1")
lbl1.pack()

print("winfo_children of frame:", frame.winfo_children())

# check if lbl1 is in winfo_children
if lbl1 in frame.winfo_children():
    print("Label 1 is in winfo_children()")
else:
    print("Label 1 is NOT in winfo_children()")
    print("Label 1 master is:", lbl1.master)
