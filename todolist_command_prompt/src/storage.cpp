#include "../include/storage.h"
#include <fstream>
#include <sstream>

bool Storage::save(const std::vector<Task>& tasks, const std::string& filename) {
    std::ofstream file(filename);
    if (!file) return false;

    for (const auto& t : tasks) {
        file << t.id << "|"
             << t.title << "|"
             << t.description << "|"
             << t.completed << "|"
             << t.priority << "|"
             << t.dueDate << "|"
             << t.createdAt << "\n";
    }
    return true;
}

std::vector<Task> Storage::load(const std::string& filename) {
    std::vector<Task> tasks;
    std::ifstream file(filename);
    if (!file) return tasks;

    std::string line;
    while (getline(file, line)) {
        std::stringstream ss(line);
        Task t;
        std::string temp;

        getline(ss, temp, '|'); t.id = std::stoi(temp);
        getline(ss, t.title, '|');
        getline(ss, t.description, '|');
        getline(ss, temp, '|'); t.completed = std::stoi(temp);
        getline(ss, temp, '|'); t.priority = std::stoi(temp);
        getline(ss, t.dueDate, '|');
        getline(ss, t.createdAt, '|');

        tasks.push_back(t);
    }

    return tasks;
}
