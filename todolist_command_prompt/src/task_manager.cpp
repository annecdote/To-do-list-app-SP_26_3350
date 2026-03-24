#include "../include/task_manager.h"
#include <ctime>

int TaskManager::nextId() {
    int maxId = 0;
    for (const auto& t : tasks)
        if (t.id > maxId) maxId = t.id;
    return maxId + 1;
}

bool TaskManager::addTask(const std::string& title,
                         const std::string& description,
                         int priority,
                         const std::string& dueDate) {

    Task t;
    t.id = nextId();
    t.title = title;
    t.description = description;
    t.completed = false;
    t.priority = priority;
    t.dueDate = dueDate;

    std::time_t now = std::time(nullptr);
    t.createdAt = std::ctime(&now);
    t.createdAt.pop_back();

    tasks.push_back(t);
    return true;
}

bool TaskManager::deleteTask(int id) {
    for (auto it = tasks.begin(); it != tasks.end(); ++it) {
        if (it->id == id) {
            tasks.erase(it);
            return true;
        }
    }
    return false;
}

bool TaskManager::markDone(int id) {
    Task* t = findTask(id);
    if (!t) return false;
    t->completed = true;
    return true;
}

bool TaskManager::markUndone(int id) {
    Task* t = findTask(id);
    if (!t) return false;
    t->completed = false;
    return true;
}

Task* TaskManager::findTask(int id) {
    for (auto& t : tasks)
        if (t.id == id) return &t;
    return nullptr;
}

std::vector<Task> TaskManager::getAll() const {
    return tasks;
}
