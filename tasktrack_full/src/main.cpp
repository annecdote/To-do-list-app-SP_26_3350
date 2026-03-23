#include "../include/task_manager.h"
#include "../include/storage.h"
#include <iostream>

void printTasks(const std::vector<Task>& tasks) {
    std::cout << "\nID  Status  Priority  Title\n";
    std::cout << "---------------------------------\n";

    for (const auto& t : tasks) {
        std::cout << t.id << "   "
                  << (t.completed ? "[x]" : "[ ]") << "     "
                  << t.priority << "         "
                  << t.title << "\n";
    }
}

int main() {
    TaskManager manager;

    auto loaded = Storage::load("tasks.txt");
    for (const auto& t : loaded)
        manager.addTask(t.title, t.description, t.priority, t.dueDate);

    std::string cmd;

    while (true) {
        std::cout << "\nCommand (add/list/done/delete/quit): ";
        std::cin >> cmd;

        if (cmd == "add") {
            std::string title;
            std::cout << "Title: ";
            std::cin.ignore();
            std::getline(std::cin, title);

            manager.addTask(title, "", 2, "");
        }
        else if (cmd == "list") {
            printTasks(manager.getAll());
        }
        else if (cmd == "done") {
            int id;
            std::cin >> id;
            manager.markDone(id);
        }
        else if (cmd == "delete") {
            int id;
            std::cin >> id;
            manager.deleteTask(id);
        }
        else if (cmd == "quit") {
            Storage::save(manager.getAll(), "tasks.txt");
            break;
        }
    }

    return 0;
}
